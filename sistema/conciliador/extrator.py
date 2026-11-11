"""Extrai os campos das capturas com o OCR nativo do Windows.
Regiões em pixels de referência (janela do processo = 1018 px de largura, análise = 1362 px),
escaladas pela largura real da captura — funciona com outra resolução/escala de tela."""
import json, re, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageOps

PS1 = Path(__file__).with_name("ocr_windows.ps1")
REF_PROC, REF_AN = 1018, 1362
REG_PROC = {"data": (126, 37, 204, 55), "pedido": (252, 37, 328, 55), "pedido2": (252, 37, 328, 55),
            "fornec": (180, 58, 548, 78),
            "sit": (757, 37, 887, 55), "itens": (7, 185, 827, 410)}
PREP_ESPECIAL = {"data", "pedido"}
COL_ITEM = (95, 500)
COL_TOTAL_ITEM = (735, 827)
COL_QTD = (500, 578)
COL_UNIT = (655, 735)
RADIO = {"Produto": (15, 51), "Serviço": (15, 78)}
REG_AN = {"titulo": (0, 0, 700, 22), "tabela": (0, 30, 1210, 520)}
AN_COL0, AN_COLW = 580, 141
ESCALA_OCR = 3


def _box(b, k): return tuple(int(v * k) for v in b)


def _prep(img, box, destino, especial=False):
    c = img.crop(box)
    if especial:
        c = c.convert("L").point(lambda v: 0 if v < 215 else 255)
        c = ImageOps.expand(c.resize((c.width * 5, c.height * 5), Image.LANCZOS), 30, fill=255)
    else:
        c = c.resize((c.width * ESCALA_OCR, c.height * ESCALA_OCR), Image.LANCZOS)
    c.save(destino); return str(destino)


def rodar_ocr(caminhos):
    with tempfile.TemporaryDirectory() as td:
        lst = Path(td) / "lista.txt"; out = Path(td) / "ocr.json"
        lst.write_text("\n".join(str(c) for c in caminhos), encoding="utf-8")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1), str(lst), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("OCR do Windows falhou: " + (r.stderr or r.stdout)[-800:])
        dados = json.loads(out.read_text(encoding="utf-8-sig") or "{}")
    return {k: (v if isinstance(v, list) else [v]) for k, v in dados.items()}


def _linhas(words, tol):
    rows = []
    for w in sorted(words, key=lambda w: (w["y"], w["x"])):
        for r in rows:
            if abs(r["y"] - w["y"]) < tol: r["w"].append(w); break
        else: rows.append({"y": w["y"], "w": [w]})
    return [(r["y"], sorted(r["w"], key=lambda w: w["x"])) for r in rows]


def _txt(ws): return " ".join(w["t"] for w in ws)


_DIG = str.maketrans({"O": "0", "o": "0", "Q": "0", "D": "0", "S": "5", "s": "5", "Z": "2", "z": "2",
                      "I": "1", "l": "1", "|": "1", "i": "1", "B": "8", "€": "6", "G": "6"})


def _cands(s):
    """Leituras possíveis de um valor: '15.000,00' -> [15000.0]; '881' (centavos perdidos) -> [881.0, 8.81]"""
    s = re.sub(r"[^\d.,]", "", (s or "").translate(_DIG))
    if not s: return []
    m = re.match(r"^(.*?)[.,](\d{2})$", s)
    if m:
        inteiro = re.sub(r"[.,]", "", m.group(1)); return [float(f"{inteiro or 0}.{m.group(2)}")]
    if re.fullmatch(r"\d+", s):
        return [float(s), int(s) / 100] if len(s) >= 3 else [float(s)]
    return []


def _num(s):
    c = _cands(s); return c[0] if len(c) == 1 else None


def _resolver(s, referencias):
    """Escolhe a leitura que bate com alguma referência (soma dos itens / subtotal)."""
    c = _cands(s)
    bate = [v for v in c if any(r and abs(v - r) < 0.05 for r in referencias)]
    if len(bate) == 1: return bate[0], False
    if len(c) == 1: return c[0], False
    return (c[0] if c else None), bool(c)


def _escuridao(img, xy, k, r=3):
    x, y = int(xy[0] * k), int(xy[1] * k)
    px = [sum(img.getpixel((i, j))[:3]) / 3 for i in range(x - r, x + r + 1) for j in range(y - r, y + r + 1)]
    return 255 - sum(px) / len(px)


def _verde_fundo(img, box, k):
    c = img.crop(_box(box, k)).convert("RGB").resize((20, 4))
    px = list(c.getdata())
    return sum(1 for (r, g, b) in px if g > 180 and r < 120 and b < 120) > len(px) * 0.3


def _verdes_por_coluna(img, k, y0, y1, ncols=5):
    cont = []
    for c in range(ncols):
        x0 = int((AN_COL0 + c * AN_COLW) * k); x1 = int((AN_COL0 + (c + 1) * AN_COLW) * k)
        if x1 > img.width: break
        reg = img.crop((x0, int(y0 * k), x1, int(y1 * k))).convert("RGB")
        px = list(reg.getdata())
        verde = sum(1 for (r, g, b) in px if g >= 100 and r < 80 and b < 80)      # preço classificado
        vermelho = sum(1 for (r, g, b) in px if r >= 180 and g < 80 and b < 80)   # preço desclassificado
        cont.append(verde - vermelho)
    return cont


def _data(ws, ate):
    t = _txt(ws).replace(" ", "").translate(_DIG)
    m = re.search(r"(\d{2})/(\d{2})", t)
    if not m: return None
    dd, mm = int(m.group(1)), int(m.group(2))
    if not (1 <= dd <= 31 and 1 <= mm <= 12): return None
    ano = ate.year - (1 if mm > ate.month + 1 else 0)
    return f"{dd:02d}/{mm:02d}/{ano}"


def extrair(capturas, pasta_tmp, ate):
    """capturas: {oc: {"processo": png, "analise": png}} -> {oc: campos + 'problemas'}"""
    pasta_tmp = Path(pasta_tmp); pasta_tmp.mkdir(parents=True, exist_ok=True)
    trabalhos, meta = [], {}
    for oc, c in capturas.items():
        p = Image.open(c["processo"]).convert("RGB"); kp = p.width / REF_PROC
        m = {"kp": kp, "tipo": max(RADIO, key=lambda t: _escuridao(p, RADIO[t], kp)),
             "aprovada": _verde_fundo(p, REG_PROC["sit"], kp)}
        for nome, b in REG_PROC.items():
            trabalhos.append(_prep(p, _box(b, kp), pasta_tmp / f"{oc}_p_{nome}.png", nome in PREP_ESPECIAL))
        if c.get("analise"):
            a = Image.open(c["analise"]).convert("RGB"); ka = a.width / REF_AN
            m["ka"] = ka; m["an_img"] = a
            for nome, b in REG_AN.items():
                trabalhos.append(_prep(a, _box(b, ka), pasta_tmp / f"{oc}_a_{nome}.png"))
        meta[oc] = m
    ocr = {Path(k).name: v for k, v in rodar_ocr(trabalhos).items()}
    res = {}
    for oc in capturas:
        g = lambda n: ocr.get(f"{oc}_{n}.png", [])
        mt = meta[oc]; prob = []
        d = {"oc": int(oc), "tipo": mt["tipo"], "aprovada": mt["aprovada"]}
        # RC
        m = re.search(r"Requisi\S*\s+de\s+Compra\s+(\d+)", _txt(g("a_titulo")), re.I)
        d["rc"] = int(m.group(1)) if m else 0
        if not m: prob.append("Sem 'Requisição de Compra' no título da Análise Comparativa (RC=0).")
        # Datas
        p1, p2 = _data(g("p_pedido"), ate), _data(g("p_pedido2"), ate)
        d["pedido"] = p1 or p2
        if p1 and p2 and p1 != p2:
            prob.append(f"Data do pedido incerta ({p1} ou {p2}); usada {p1}.")
        if not d["pedido"]:
            d["pedido"] = _data(g("p_data"), ate)
            prob.append("Data do pedido não lida; usada a data do processo." if d["pedido"] else "Data do pedido não lida.")
        # Situação / aprovação
        sit = _txt(g("p_sit"))
        d["situacao"] = "Ordem de Compra" if re.search(r"ordem", sit, re.I) else (sit.strip() or "?")
        if not d["aprovada"]: prob.append("Situação não está em verde no ERP (pode não estar aprovada).")
        # Fornecedor
        fz = re.sub(r"^\s*\d+\s*", "", _txt(g("p_fornec")))
        d["fornecedor_erp"] = re.split(r"\s*\(", fz)[0].strip(" |•.-") or None
        if not d["fornecedor_erp"]: prob.append("Fornecedor não lido.")
        # Itens e soma dos totais dos itens
        k = mt["kp"] * ESCALA_OCR; off = REG_PROC["itens"][0]
        itens, somas, soma_qxu = [], {0.0}, 0.0
        BORDA = {"|", "I", "l", "!", "1|", "|1"}  # linhas da grade lidas como caractere
        col = lambda ln, a, b: "".join(w["t"] for w in ln if (a - off) * k <= w["x"] < (b - off) * k and w["t"] not in BORDA)
        for _, ln in _linhas(g("p_itens"), tol=9 * ESCALA_OCR):
            nome = " ".join(w["t"] for w in ln if (COL_ITEM[0] - off) * k <= w["x"] < (COL_ITEM[1] - off) * k)
            nome = re.sub(r"\[?N[CE]M.*$", "", nome).strip(" |'\"•.")
            if nome and nome.lower() != "item":
                itens.append(nome)
                cs = _cands(col(ln, COL_TOTAL_ITEM[0], 2000))
                # quantidade (a borda da grade às vezes vira '1' no fim) x unitário confirma o total do item
                q = re.sub(r"\D", "", col(ln, *COL_QTD).translate(_DIG).split(",")[0])
                qs = {int(q)} | ({int(q[:-1])} if len(q) > 1 and q.endswith("1") else set()) if q else set()
                us = _cands(col(ln, *COL_UNIT))
                conf = {round(a * b, 2) for a in qs for b in us if any(abs(a * b - c) < 0.05 for c in cs)}
                if len(conf) == 1: cs = list(conf)
                somas = {round(s + c, 2) for s in somas for c in cs} if (cs and somas and len(somas) < 64) else set()
                if soma_qxu is not None and len(conf) == 1: soma_qxu += next(iter(conf))
                else: soma_qxu = None
        d["itens"] = itens
        d["soma_qxu"] = round(soma_qxu, 2) if soma_qxu else None
        if d["soma_qxu"] and any(abs(d["soma_qxu"] - s) < 0.05 for s in somas): somas = {d["soma_qxu"]}
        d["soma_itens"] = next(iter(somas)) if len(somas) == 1 else None
        somas_possiveis = list(somas)
        if not itens: prob.append("Itens não lidos.")
        # Análise: coluna vencedora (preço verde) -> TOTAL, SUBTOTAL, Condições
        d["valor"] = d["subtotal"] = d["pagamento"] = None
        if "ka" in mt:
            ka = mt["ka"]; kk = ka * ESCALA_OCR; y0 = REG_AN["tabela"][1]
            linhas = _linhas(g("a_tabela"), tol=9 * ESCALA_OCR)
            y_sub = next((y for y, ln in linhas if _txt(ln).replace(" ", "").upper().startswith("SUBTOTAL")), None)
            col = 0
            # 1º critério: coluna cujo cabeçalho é o fornecedor desta OC; 2º: preço verde (classificado)
            cab = {}
            if linhas:
                for w in linhas[0][1]:
                    if w["x"] / kk >= AN_COL0 - 2:
                        cab.setdefault(int((w["x"] / kk - AN_COL0) // AN_COLW), []).append(w["t"])
            chave = re.sub(r"[^A-Z0-9]", "", (d.get("fornecedor_erp") or "").upper())[:8]
            por_nome = [c for c, ws in cab.items() if chave and re.sub(r"[^A-Z0-9]", "", "".join(ws).upper())[:8] == chave]
            if y_sub is not None:
                verdes = _verdes_por_coluna(mt["an_img"], ka, y0 + 18, y0 + y_sub / kk)
                d["cotacoes"] = len(verdes) if verdes else 1
                col_verde = verdes.index(max(verdes)) if verdes and max(verdes) > 0 else None
                if len(por_nome) == 1:
                    col = por_nome[0]
                    if col_verde is not None and col_verde != col:
                        prob.append("A cotação vencedora (verde) na Análise é de outro fornecedor — conferir.")
                elif col_verde is not None:
                    col = col_verde
                    if len(cab) > 1: prob.append(f"Fornecedor não localizado no cabeçalho da Análise; usada a coluna verde ({col + 1}).")
            d["coluna_vencedora"] = col + 1
            def na_coluna(ln):
                return [w for w in ln if int((w["x"] / kk - AN_COL0) // AN_COLW) == col and w["x"] / kk >= AN_COL0 - 2]
            brutos = {}
            for y, ln in linhas:
                rot = _txt([w for w in ln if w["x"] / kk < AN_COL0 - 30]).replace(" ", "").upper()
                val = na_coluna(ln)
                if rot.startswith("SUBTOTAL") and val: brutos["sub"] = "".join(w["t"] for w in val)
                elif rot.startswith("TOTAL") and val:
                    brutos["tot"] = "".join(w["t"] for w in val)
                    por_col = {}
                    for w in ln:
                        if w["x"] / kk >= AN_COL0 - 2:
                            por_col.setdefault(int((w["x"] / kk - AN_COL0) // AN_COLW), []).append(w["t"])
                    d["totais_cotacoes"] = [_num("".join(v)) for _, v in sorted(por_col.items())]
                elif rot.startswith("CONDI") and val: d["pagamento"] = _txt(val)
            if "sub" in brutos: d["subtotal"], _ = _resolver(brutos["sub"], somas_possiveis)
            if d["subtotal"] and not d["soma_itens"] and any(abs(d["subtotal"] - s) < 0.05 for s in somas_possiveis):
                d["soma_itens"] = d["subtotal"]
            if "tot" in brutos:
                d["valor"], ambiguo = _resolver(brutos["tot"], [d["subtotal"]] + somas_possiveis)
                if ambiguo: prob.append(f"Valor lido como '{brutos['tot']}' (ambíguo) — conferir.")
        if d["valor"] is None: prob.append("Valor TOTAL não lido na Análise Comparativa.")
        elif d["soma_itens"] and abs(d["soma_itens"] - d["valor"]) > 0.05:
            prob.append(f"Valor ({d['valor']:.2f}) difere da soma dos itens ({d['soma_itens']:.2f}) — desconto/frete ou leitura a conferir.")
        if d["pagamento"] is None: prob.append("Condições de pagamento não lidas.")
        if d["subtotal"] and d["valor"] and d["subtotal"] - d["valor"] > 0.05:
            d["possivel_saving"] = round(d["subtotal"] - d["valor"], 2)
        d["problemas"] = prob
        res[oc] = d
    return res


def texto_pagamento(pagamento, emp):
    """'15 dias Direto' -> '15 dias'; 'A VISTA' -> texto_a_vista; '30/60 dias' -> '30/60 dias'"""
    if not pagamento: return None
    if re.search(r"vista", pagamento, re.I): return emp["texto_a_vista"]
    m = re.search(r"(\d+(?:\s*/\s*\d+)*)\s*d[il1]as?", pagamento, re.I)
    if m:
        n = re.sub(r"\s", "", m.group(1))
        return emp["texto_a_vista"] if n == "0" else emp["texto_prazo"].format(n=n)
    return pagamento.strip()
