"""Coleta no Minerion SGA — SOMENTE CONSULTA.
Teclas usadas: menu (Alt+setas), F5 (pesquisar), HOME/DOWN (andar na lista), ENTER (abrir a partir da lista),
F9 (Análise Comparativa), ESC (fechar/cancelar). Nunca Grava, Aprova, Reprova, Exclui ou Seleciona."""
import json, re, time
from . import tela

LARG_PESQUISA = 1018  # largura de referência da janela "Pesquisa de Processos de Compra"
CAMPO_DATA_INI = (118, 73)  # posição de referência do 1º campo de data


class Abortado(Exception):
    pass


def _log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def verificar_empresa(emp):
    principais = [(t, w) for t, w in tela.janelas() if t.startswith("Minerion SGA - ")]
    if not principais:
        raise Abortado("Janela principal do Minerion não encontrada. Abra o Minerion SGA.")
    if len(principais) > 1:
        raise Abortado("Há mais de uma empresa aberta no Minerion (" + "; ".join(t for t, _ in principais) +
                       "). Feche as outras e deixe só a empresa que vai conciliar.")
    t, w = principais[0]
    if emp["titulo_erp"].lower() not in t.lower():
        raise Abortado(f"O Minerion está na empresa errada: '{t}'. Troque para a empresa que contém '{emp['titulo_erp']}'.")
    return w


def abrir_pesquisa(cfg, de, ate):
    """Garante a 'Pesquisa de Processos de Compra' aberta e filtrada pelo período."""
    t, pesq = tela.achar("Pesquisa de Processos")
    if not pesq:
        t, dlg = tela.achar("Processos de Compra")
        if not dlg:
            _, main = tela.achar("Minerion SGA - ")
            tela.focar(main)
            from pywinauto import keyboard
            keyboard.send_keys(cfg["erp"]["teclas_menu_processos"], pause=0.08)
            t, dlg = tela.esperar("Processos de Compra", 8)
            if not dlg: raise Abortado("Não consegui abrir 'Processos de Compra' pelo menu (ajuste 'teclas_menu_processos').")
        tela.teclas(dlg, "{F5}")
        t, pesq = tela.esperar("Pesquisa de Processos", 10)
        if not pesq: raise Abortado("A pesquisa (F5) não abriu.")
    # datas
    tela.clicar_rel(pesq, *CAMPO_DATA_INI, LARG_PESQUISA); time.sleep(0.3)
    from pywinauto import keyboard
    keyboard.send_keys("{HOME}" + de.strftime("%d%m%Y") + "{TAB}{HOME}" + ate.strftime("%d%m%Y"), pause=0.05)
    time.sleep(0.4)
    tela.teclas(pesq, "{F5}"); time.sleep(4)
    return pesq


def _fechar_tudo_ate_pesquisa():
    for _ in range(6):
        if not (tela.achar("Análise comparativa")[1] or tela.achar("Processo de Compra ")[1] or tela.achar("Rateio de Servi")[1]):
            return True
        for pref in ("Análise comparativa", "Rateio de Servi", "Processo de Compra "):
            t, w = tela.achar(pref)
            if w: tela.teclas(w, "{ESC}"); time.sleep(1.2); break
    return tela.achar("Pesquisa de Processos")[1] is not None


def coletar(cfg, emp, de, ate, pasta, ocs_existentes, limite=None):
    """Percorre a lista da pesquisa. Para cada OC nova salva 2 capturas (processo e análise)."""
    verificar_empresa(emp)
    pesq = abrir_pesquisa(cfg, de, ate)
    estado_p = pasta / "coleta.json"
    estado = json.loads(estado_p.read_text(encoding="utf-8")) if estado_p.exists() else {"ocs": {}, "puladas": []}
    tela.teclas(pesq, "{HOME}"); time.sleep(0.6)
    anterior, i, novas = None, 0, 0
    while True:
        t, pesq = tela.achar("Pesquisa de Processos")
        if not pesq: raise Abortado("A janela de pesquisa sumiu.")
        if i > 0: tela.teclas(pesq, "{DOWN}"); time.sleep(0.35)
        tela.teclas(pesq, "{ENTER}")
        titulo, proc = tela.esperar("Processo de Compra ", 12)
        if not proc: raise Abortado("O processo não abriu (Enter na lista).")
        m = re.search(r"Processo de Compra (\d+)", titulo); oc = m.group(1) if m else None
        if oc is None or oc == anterior:  # fim da lista
            _fechar_tudo_ate_pesquisa(); break
        anterior, i = oc, i + 1
        if oc in ocs_existentes or oc in estado["ocs"]:
            estado["puladas"].append(oc) if oc not in estado["puladas"] else None
            _fechar_tudo_ate_pesquisa(); continue
        time.sleep(cfg["erp"]["espera_abrir_s"])
        cap_p = tela.capturar(proc, str(pasta / "capturas" / f"{oc}_processo.png"))
        tela.teclas(proc, "{F9}")
        ta, an = tela.esperar("Análise comparativa", 12)
        cap_a = None
        if an:
            time.sleep(cfg["erp"]["espera_abrir_s"])
            cap_a = tela.capturar(an, str(pasta / "capturas" / f"{oc}_analise.png"))
        if not _fechar_tudo_ate_pesquisa():
            raise Abortado(f"Não consegui voltar para a pesquisa depois da OC {oc}.")
        estado["ocs"][oc] = {"titulo": titulo, "processo": cap_p, "analise": cap_a}
        estado_p.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        novas += 1; _log(f"OC {oc} capturada")
        if limite and novas >= limite: break
    _log(f"Coleta concluída: {novas} novas, {len(estado['puladas'])} já estavam na planilha.")
    return estado
