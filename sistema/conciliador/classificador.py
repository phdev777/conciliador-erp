"""Sugere 'Linha do Pacote' e o nome de fornecedor a partir do HISTÓRICO da própria planilha."""
import re, unicodedata
from collections import Counter

STOP = {"LTDA", "ME", "EPP", "EIRELI", "SA", "S/A", "COMERCIO", "COMERCIAL", "DE", "DA", "DO", "DOS", "DAS", "E", "EM",
        "SERVICOS", "SERVICO", "INDUSTRIA", "INDUSTRIAL", "DISTRIBUIDORA", "LIMITADA", "CIA", "PARA", "COM", "DER",
        "REPRESENTACOES", "IMPORTACAO", "EXPORTACAO", "PECAS", "EQUIPAMENTOS", "SOLUCOES", "TECNOLOGIA", "AUTO", "POSTO"}
STOP_ITEM = {"PARA", "COM", "SEM", "TIPO", "MODELO", "SERIE", "UNIDADE", "LITROS", "PECA", "PECAS", "SERVICO", "SERVICOS",
             "MATERIAL", "MATERIAIS", "DIANT", "TRAS", "LADO"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]", " ", s)


def tokens(s, stop, minimo=4):
    return [t for t in norm(s).split() if len(t) >= minimo and t not in stop and not t.isdigit()]


def limpar_ocr(s):
    """Correções comuns de OCR em nomes (Ü->O, 4->A dentro de palavras, ...CUO->...CAO)."""
    s = (s or "").replace("Ü", "O").replace("ü", "O").replace("•", "-")
    s = re.sub(r"(?<=[A-Z])4(?=[A-Z])", "A", s)
    s = re.sub(r"CU([OÕ])\b", r"CA\1", s)
    s = re.sub(r"\bS[S5][O0][O0]\b", "S500", s, flags=re.I)            # diesel S500 lido como SSOO
    s = re.sub(r"\bS[.\-]?\s?[l1I|]\s?[O0]\b", "S10", s, flags=re.I)   # diesel S10 lido como s.l O
    s = re.sub(r"NCU\b", "NCA", s)                                      # SEGURANCU -> SEGURANCA
    return re.sub(r"\s+", " ", s).strip(" -.|")


class Classificador:
    def __init__(self, historico, linhas_validas):
        """historico: lista de (fornecedor, item, linha_pacote); linhas_validas: valores da aba Base de Dados."""
        self.hist = [(norm(f), norm(i), str(l).strip(), str(f).strip()) for f, i, l in historico if l and str(l).strip()]
        self.validas = {norm(v).strip(): str(v).strip() for v in linhas_validas if v}

    def _valida(self, linha):
        return norm(linha).strip() in self.validas

    def sugerir(self, fornecedor_erp, itens):
        # a 1ª palavra distintiva do fornecedor tem que ser a 1ª palavra distintiva do nome no histórico
        tf = tokens(limpar_ocr(fornecedor_erp), STOP)[:1]
        ti = tokens(limpar_ocr(" ".join(itens[:2])), STOP_ITEM, 3)[:3]
        por_f = [r for r in self.hist if tf and tokens(r[3], STOP)[:1] == tf]
        por_i = [r for r in self.hist if ti and any(t in r[1].split() for t in ti)]
        ambos = [r for r in por_f if any(t in r[1].split() for t in ti)]
        nome = Counter(r[3] for r in por_f).most_common(1)
        nome = nome[0][0] if nome else None
        for origem, rows in (("fornecedor e item", ambos), ("fornecedor", por_f), ("item", por_i)):
            c = Counter(r[2] for r in rows if self._valida(r[2]))
            if not c: continue
            # junta grafias diferentes da mesma linha (OLEO DIESEL S10 / Oleo Diesel S10)
            agrup = Counter()
            for l, n in c.items(): agrup[norm(l).strip()] += n
            chave, n = agrup.most_common(1)[0]
            total = sum(agrup.values())
            grafia = max((l for l in c if norm(l).strip() == chave), key=lambda l: c[l])
            confiante = n >= 2 and n / total >= 0.6
            top = ", ".join(f"{self.validas.get(k, k)} ({v}x)" for k, v in agrup.most_common(3))
            motivo = f"Histórico por {origem}: {top}."
            return {"linha": grafia, "confiante": confiante, "motivo": motivo, "fornecedor": nome}
        return {"linha": None, "confiante": False, "motivo": "Sem histórico para este fornecedor/item.", "fornecedor": nome}


def resumo_itens(itens, maximo=3, tam=70):
    limpos = []
    for i in itens[:maximo]:
        i = limpar_ocr(re.sub(r"\[?N[CE]M.*$", "", i))
        i = re.sub(r"\s*\(.*?\)\s*", " ", i).strip()
        if i: limpos.append(i.capitalize())
    s = "/".join(limpos)
    return s[:tam] if s else None
