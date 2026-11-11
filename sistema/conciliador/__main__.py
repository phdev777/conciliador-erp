"""Uso:  python -m conciliador <comando> --empresa <nome> [opções]

Comandos
  diagnostico            confere Python, OCR do Windows, Excel, Minerion e monitores
  coletar                lê as OCs no Minerion (somente consulta) e salva capturas
  extrair                lê as capturas com o OCR do Windows -> extracao.json
  lotes                  gera imagens de revisão (método com Claude)
  lancar [--simular]     acrescenta as OCs na planilha aberta no Excel + relatório
  tudo                   coletar + extrair + lancar (método sem Claude)

Opções
  --empresa NOME         chave do config.json (ex.: empresa1)
  --de DD/MM/AAAA        início do período (padrão: dia 1 do mês atual)
  --ate DD/MM/AAAA       fim do período (padrão: hoje)
  --execucao PASTA       usa uma coleta específica (padrão: a mais recente da empresa)
  --limite N             para depois de N OCs novas (teste)
"""
import argparse, datetime, json, sys, shutil
from pathlib import Path
from . import config as C


def _data(s): return datetime.datetime.strptime(s, "%d/%m/%Y").date()


def _args():
    ap = argparse.ArgumentParser(prog="conciliador", add_help=True, description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["diagnostico", "coletar", "extrair", "lotes", "lancar", "tudo"])
    ap.add_argument("--empresa"); ap.add_argument("--de", type=_data); ap.add_argument("--ate", type=_data)
    ap.add_argument("--execucao"); ap.add_argument("--limite", type=int); ap.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    hoje = datetime.date.today()
    a.ate = a.ate or hoje; a.de = a.de or a.ate.replace(day=1)
    if a.comando != "diagnostico" and not a.empresa:
        ap.error("informe --empresa")
    return a


def diagnostico(cfg):
    ok = True
    print("Config:", C.caminho_config())
    print("Dados:", C.pasta_dados())
    try:
        from . import tela
        tit = [t for t, _ in tela.janelas() if "Minerion" in t]
        print("Minerion:", tit or "NÃO ENCONTRADO (abra o ERP)")
    except Exception as e:
        ok = False; print("pywinauto: ERRO", e)
    try:
        import ctypes; u = ctypes.windll.user32
        print(f"Área virtual da tela: x={u.GetSystemMetrics(76)} y={u.GetSystemMetrics(77)} "
              f"{u.GetSystemMetrics(78)}x{u.GetSystemMetrics(79)}")
    except Exception: pass
    try:
        import win32com.client as w
        xl = w.GetActiveObject("Excel.Application"); print("Excel aberto:", [b.Name for b in xl.Workbooks])
    except Exception:
        print("Excel: fechado (abra a planilha antes de 'lancar')")
    try:
        from . import extrator
        from PIL import Image
        tmp = C.pasta_dados() / "_teste_ocr.png"
        img = Image.new("RGB", (400, 60), "white")
        from PIL import ImageDraw; ImageDraw.Draw(img).text((10, 20), "Teste 123 OCR", fill="black")
        img = img.resize((1200, 180)); img.save(tmp)
        r = extrator.rodar_ocr([tmp]); print("OCR do Windows: OK ->", " ".join(w["t"] for w in list(r.values())[0]))
        tmp.unlink(missing_ok=True)
    except Exception as e:
        ok = False; print("OCR do Windows: ERRO", e)
    print("Empresas configuradas:", ", ".join(cfg["empresas"]))
    return ok


def main():
    a = _args(); cfg = C.carregar()
    if a.comando == "diagnostico":
        sys.exit(0 if diagnostico(cfg) else 1)
    emp = C.empresa(cfg, a.empresa)

    if a.comando in ("coletar", "tudo"):
        from . import erp
        existentes = set()
        try:
            from .planilha import Planilha
            existentes = Planilha(cfg, emp).ocs_existentes()
            print(f"Planilha aberta: {len(existentes)} OCs já lançadas serão puladas.")
        except SystemExit as e:
            print(f"Aviso: {e} — a coleta vai capturar todas; a duplicidade é conferida de novo no lançamento.")
        pasta = Path(a.execucao) if a.execucao else C.nova_execucao(a.empresa)
        (pasta / "parametros.json").write_text(json.dumps({"empresa": a.empresa, "de": str(a.de), "ate": str(a.ate)}), encoding="utf-8")
        print("Pasta da execução:", pasta)
        print(">>> NÃO mexa no mouse/teclado até terminar. <<<")
        try:
            erp.coletar(cfg, emp, a.de, a.ate, pasta, existentes, a.limite)
        except erp.Abortado as e:
            print("COLETA INTERROMPIDA:", e, "\nO que já foi capturado está salvo; rode de novo com --execucao", pasta); sys.exit(2)
        a.execucao = str(pasta)

    pasta = Path(a.execucao) if a.execucao else C.ultima_execucao(a.empresa)
    par = json.loads((pasta / "parametros.json").read_text(encoding="utf-8")) if (pasta / "parametros.json").exists() else {}
    ate = _data(datetime.date.fromisoformat(par["ate"]).strftime("%d/%m/%Y")) if par.get("ate") else a.ate

    if a.comando in ("extrair", "tudo", "lotes"):
        from . import extrator
        if a.comando != "lotes" or not (pasta / "extracao.json").exists():
            caps = json.loads((pasta / "coleta.json").read_text(encoding="utf-8"))["ocs"]
            caps = {oc: c for oc, c in caps.items() if c.get("processo")}
            print(f"Lendo {len(caps)} OCs com o OCR do Windows...")
            ext = extrator.extrair(caps, pasta / "ocr_tmp", ate)
            (pasta / "extracao.json").write_text(json.dumps(ext, ensure_ascii=False, indent=1), encoding="utf-8")
            shutil.rmtree(pasta / "ocr_tmp", ignore_errors=True)
            print("Extração salva:", pasta / "extracao.json")
        if a.comando == "lotes":
            from .fluxo import lotes_revisao
            ext = json.loads((pasta / "extracao.json").read_text(encoding="utf-8"))
            for f in lotes_revisao(pasta, ext): print(f)
            print("Revise e corrija em:", pasta / "extracao.json"); return

    if a.comando in ("lancar", "tudo"):
        from .planilha import Planilha
        from .fluxo import montar, relatorio
        arq = pasta / "extracao.json"
        if not arq.exists(): raise SystemExit("Rode 'extrair' antes de 'lancar'.")
        ext = json.loads(arq.read_text(encoding="utf-8"))
        pl = Planilha(cfg, emp)
        regs, fora = montar(ext, emp, cfg, pl.ler(), pl.linhas_validas())
        feitos, pulados = pl.acrescentar(regs, simular=a.simular)
        txt = relatorio(pasta, emp["planilha"] + (" (SIMULAÇÃO)" if a.simular else ""), feitos, pulados, fora, regs)
        print(txt)
        if a.simular:
            (pasta / "simulacao.json").write_text(json.dumps(regs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
