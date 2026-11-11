"""Leitura/escrita na planilha ABERTA no Excel (inclusive aberta pelo SharePoint/OneDrive com salvamento automático).
Só ACRESCENTA linhas no fim; nunca substitui o arquivo nem altera linhas existentes."""
import datetime, time

OCUPADO = -2146777998  # "O Excel está ocupado" (célula em edição, carregando...)


def _col(letra):
    n = 0
    for ch in letra.upper(): n = n * 26 + ord(ch) - 64
    return n


def _retry(f, tentativas=40):
    import pywintypes
    for _ in range(tentativas):
        try:
            return f()
        except pywintypes.com_error as e:
            if e.excepinfo and e.excepinfo[5] == OCUPADO:
                time.sleep(1.5); continue
            raise
    raise RuntimeError("O Excel ficou ocupado por muito tempo (há alguma célula em edição?).")


class Planilha:
    def __init__(self, cfg, emp):
        import win32com.client as w
        self.cfg, self.emp, self.pc = cfg, emp, cfg["planilha"]
        try:
            self.xl = w.GetActiveObject("Excel.Application")
        except Exception:
            raise SystemExit(f"Abra a planilha '{emp['planilha']}' no Excel antes de continuar.")
        self.wb = next((b for b in self.xl.Workbooks if b.Name.lower() == emp["planilha"].lower()), None)
        if self.wb is None:
            raise SystemExit(f"A planilha '{emp['planilha']}' não está aberta no Excel.")
        self.ws = self.wb.Worksheets(emp["aba"])
        self.c = {k: _col(v) for k, v in self.pc["colunas"].items()}

    def ultima_linha(self):
        return _retry(lambda: self.ws.Cells(self.ws.Rows.Count, self.c["data_pedido"]).End(-4162).Row)

    def ler(self):
        """Retorna lista de dicts das linhas preenchidas (para duplicidade e histórico)."""
        ini = self.pc["linha_cabecalho"] + 1; fim = self.ultima_linha()
        if fim < ini: return []
        ncol = max(self.c.values())
        dados = _retry(lambda: self.ws.Range(self.ws.Cells(ini, 1), self.ws.Cells(fim, ncol)).Value)
        inv = {v: k for k, v in self.c.items()}
        out = []
        for i, row in enumerate(dados):
            d = {inv[j + 1]: v for j, v in enumerate(row) if (j + 1) in inv}
            d["_linha"] = ini + i; out.append(d)
        return out

    def ocs_existentes(self):
        out = set()
        for r in self.ler():
            v = r.get("oc")
            if v not in (None, ""):
                out.add(str(int(v)) if isinstance(v, float) else str(v).strip())
        return out

    def linhas_validas(self):
        try:
            ws = self.wb.Worksheets(self.pc["aba_base_dados"])
            fim = _retry(lambda: ws.Cells(ws.Rows.Count, 1).End(-4162).Row)
            vals = _retry(lambda: ws.Range(ws.Cells(1, 1), ws.Cells(fim, 1)).Value)
            return [r[0] for r in vals if r[0]]
        except Exception:
            return []

    def acrescentar(self, registros, simular=False):
        """registros: lista de dicts {campo: valor, '_notas': {campo: texto}}. Retorna [(oc, linha)]."""
        existentes = self.ocs_existentes()
        linha = self.ultima_linha() + 1
        feitos, pulados = [], []
        for reg in registros:
            oc = str(reg["oc"])
            if oc in existentes: pulados.append(oc); continue
            ocupadas = [k for k, c in self.c.items() if k not in ("mes_ano", "sla", "pacote")
                        and _retry(lambda c=c: self.ws.Cells(linha, c).Text).strip()]
            if ocupadas:
                raise RuntimeError(f"A linha {linha} não está vazia ({ocupadas}). Nada foi sobrescrito.")
            if simular:
                feitos.append((oc, linha)); linha += 1; continue
            for campo, valor in reg.items():
                if campo.startswith("_") or valor in (None, "") or campo not in self.c: continue
                cel = self.ws.Cells(linha, self.c[campo])
                if isinstance(valor, datetime.date):
                    serial = (datetime.datetime(valor.year, valor.month, valor.day) - datetime.datetime(1899, 12, 30)).days
                    _retry(lambda: setattr(cel, "Value2", serial))
                    fmt = _retry(lambda: self.ws.Cells(linha - 1, self.c[campo]).NumberFormat)
                    _retry(lambda: setattr(cel, "NumberFormat", fmt))
                else:
                    _retry(lambda: setattr(cel, "Value", valor))
            for letra in self.pc["colunas_formula"]:  # recoloca fórmulas que faltarem
                alvo = self.ws.Range(f"{letra}{linha}")
                if not str(_retry(lambda: alvo.Formula)).startswith("="):
                    _retry(lambda: self.ws.Range(f"{letra}{linha - 1}").Copy())
                    _retry(lambda: alvo.PasteSpecial(-4123))
                    self.xl.CutCopyMode = False
            for campo, texto in reg.get("_notas", {}).items():
                if campo in self.c:
                    cel = self.ws.Cells(linha, self.c[campo])
                    _retry(lambda: cel.ClearComments())
                    _retry(lambda: cel.AddComment(self.pc["prefixo_anotacao"] + texto))
            feitos.append((oc, linha)); existentes.add(oc); linha += 1
        if not simular and feitos:
            _retry(lambda: self.wb.Save())
        return feitos, pulados
