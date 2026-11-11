"""Monta os registros da planilha a partir da extração, e gera relatório e lotes de revisão."""
import datetime, json
from pathlib import Path
from PIL import Image, ImageDraw
from . import extrator
from .classificador import Classificador, resumo_itens, limpar_ocr

# em qual coluna cada tipo de problema vira anotação
NOTA_CAMPO = [("Requisi", "rc"), ("pedido", "data_pedido"), ("verde", "oc"), ("Valor", "valor"),
              ("pagamento", "forma_pagamento"), ("Fornecedor", "fornecedor"), ("Itens", "item"),
              ("cotação", "valor")]


def montar(extracao, emp, cfg, planilha_hist, linhas_validas):
    cls = Classificador([(r.get("fornecedor"), r.get("item"), r.get("linha_pacote")) for r in planilha_hist], linhas_validas)
    situacoes = [s.lower() for s in cfg["erp"]["lancar_situacoes"]]
    regs, fora = [], []
    for oc, d in sorted(extracao.items(), key=lambda kv: int(kv[0])):
        if d.get("situacao", "").lower() not in situacoes:
            fora.append((oc, f"Situação '{d.get('situacao')}' não é lançada")); continue
        sug = cls.sugerir(d.get("fornecedor_erp") or "", d.get("itens") or [])
        notas = {}
        for p in d.get("problemas", []):
            campo = next((c for chave, c in NOTA_CAMPO if chave.lower() in p.lower()), "oc")
            notas[campo] = (notas[campo] + " | " if campo in notas else "") + p
        if sug["linha"] and not sug["confiante"]:
            notas["linha_pacote"] = f"Linha do Pacote preenchida por sugestão ({sug['linha']}). {sug['motivo']}"
        elif not sug["linha"]:
            notas["linha_pacote"] = sug["motivo"] + " Preencher manualmente."
        if d.get("possivel_saving"):
            notas["saving"] = f"Possível saving: subtotal {d['subtotal']:.2f} − compra {d['valor']:.2f} = {d['possivel_saving']:.2f}. Não preenchido (regra não definida)."
        ped = d.get("pedido")
        regs.append({
            "oc": int(oc), "rc": d.get("rc", 0),
            "data_pedido": datetime.datetime.strptime(ped, "%d/%m/%Y").date() if ped else None,
            "forma_pagamento": extrator.texto_pagamento(d.get("pagamento"), emp),
            "tipo": d.get("tipo"), "valor": d.get("valor"), "solicitante": emp["solicitante"],
            "linha_pacote": sug["linha"], "item": resumo_itens(d.get("itens") or []),
            "fornecedor": sug["fornecedor"] or limpar_ocr(d.get("fornecedor_erp") or "") or None,
            "_notas": notas,
        })
    return regs, fora


def relatorio(pasta, empresa, feitos, pulados, fora, regs):
    linhas = [f"Conciliador ERP — {empresa} — {datetime.datetime.now():%d/%m/%Y %H:%M}", "",
              f"Lançadas na planilha: {len(feitos)}"]
    por_oc = {str(r['oc']): r for r in regs}
    for oc, ln in feitos:
        n = por_oc.get(oc, {}).get("_notas", {})
        linhas.append(f"  OC {oc} -> linha {ln}" + (f"   [conferir: {', '.join(n)}]" if n else ""))
    linhas += ["", f"Já estavam na planilha (puladas): {len(pulados)}  {', '.join(pulados)}",
               f"Não lançadas: {len(fora)}"] + [f"  OC {oc}: {m}" for oc, m in fora]
    pend = [(r["oc"], r["_notas"]) for r in regs if r["_notas"]]
    linhas += ["", f"Com anotação para conferência: {len(pend)}"]
    for oc, n in pend:
        for campo, t in n.items(): linhas.append(f"  OC {oc} [{campo}]: {t}")
    txt = "\n".join(linhas)
    (Path(pasta) / "relatorio.txt").write_text(txt, encoding="utf-8")
    return txt


def lotes_revisao(pasta, extracao, por_lote=4):
    """Para o método com Claude: imagens compactas (processo + análise) com o que o OCR leu, para revisão."""
    pasta = Path(pasta); out = pasta / "revisao"; out.mkdir(exist_ok=True)
    cols = json.loads((pasta / "coleta.json").read_text(encoding="utf-8"))["ocs"]
    ocs = sorted(extracao, key=int); arquivos = []
    for i in range(0, len(ocs), por_lote):
        grupo = ocs[i:i + por_lote]; altura = 300
        img = Image.new("RGB", (1470, altura * len(grupo)), "white"); dr = ImageDraw.Draw(img)
        for j, oc in enumerate(grupo):
            p = Image.open(cols[oc]["processo"]).convert("RGB"); kp = p.width / extrator.REF_PROC
            y = altura * j
            img.paste(p.crop((0, 0, int(890 * kp), int(120 * kp))).resize((890, 120)), (0, y))
            img.paste(p.crop((0, int(185 * kp), int(830 * kp), int(300 * kp))).resize((830, 115)), (0, y + 120))
            if cols[oc].get("analise"):
                a = Image.open(cols[oc]["analise"]).convert("RGB"); ka = a.width / extrator.REF_AN
                img.paste(a.crop((0, 0, int(700 * ka), int(22 * ka))).resize((700, 22)), (0, y + 238))
                img.paste(a.crop((0, int(30 * ka), int(130 * ka), int(300 * ka))).resize((130, 270)), (895, y))
                img.paste(a.crop((int(580 * ka), int(30 * ka), int(1020 * ka), int(300 * ka))).resize((440, 270)), (1028, y))
            d = extracao[oc]
            dr.text((5, y + 262), f"OCR -> OC {oc} | RC {d.get('rc')} | pedido {d.get('pedido')} | {d.get('tipo')} | "
                                  f"valor {d.get('valor')} | pgto {d.get('pagamento')} | forn {d.get('fornecedor_erp')}", fill="blue")
            dr.line((0, y + altura - 2, 1470, y + altura - 2), fill="red", width=2)
        f = out / f"lote_{i // por_lote + 1:02d}.png"; img.save(f); arquivos.append(str(f))
    return arquivos
