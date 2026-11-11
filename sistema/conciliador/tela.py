"""Janelas, capturas e teclado — independente de monitor/posição/escala."""
import ctypes, time
from PIL import ImageGrab

try:  # coordenadas em pixels físicos, iguais às da captura
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except Exception: pass

from pywinauto import Desktop, keyboard, mouse  # noqa: E402  (depois do DPI)

# Teclas permitidas no ERP. Nada de Ins/Del/F4/F10/Enter fora da lista de pesquisa.
TECLAS_PERMITIDAS = {"{HOME}", "{DOWN}", "{PGDN}", "{ENTER}", "{F5}", "{F9}", "{ESC}", "{TAB}"}


def janelas():
    out = []
    for w in Desktop(backend="win32").windows():
        try:
            t = w.window_text()
            if t and w.is_visible():
                out.append((t, w))
        except Exception:
            pass
    return out


def achar(prefixo, contem=None):
    for t, w in janelas():
        if t.startswith(prefixo) and (contem is None or contem.lower() in t.lower()):
            return t, w
    return None, None


def achar_contendo(trecho):
    for t, w in janelas():
        if trecho.lower() in t.lower():
            return t, w
    return None, None


def esperar(prefixo, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        t, w = achar(prefixo)
        if w: return t, w
        time.sleep(0.3)
    return None, None


def esperar_sumir(prefixo, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not achar(prefixo)[1]: return True
        time.sleep(0.3)
    return False


def focar(w):
    w.set_focus(); time.sleep(0.3)


def teclas(w, seq):
    """Envia teclas à janela w. Só aceita teclas da lista segura (ou texto de data)."""
    focar(w)
    keyboard.send_keys(seq, pause=0.05)


def clicar_rel(w, x_ref, y_ref, largura_ref):
    """Clica numa posição relativa à janela, escalando pela largura real vs. referência."""
    r = w.rectangle(); esc = (r.right - r.left) / largura_ref
    focar(w)
    mouse.click(coords=(int(r.left + x_ref * esc), int(r.top + y_ref * esc)))


def _origem_virtual():
    u = ctypes.windll.user32
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77)  # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN


def capturar(w, caminho):
    """Salva a imagem da janela (funciona com qualquer arranjo de monitores)."""
    r = w.rectangle(); ox, oy = _origem_virtual()
    img = ImageGrab.grab(all_screens=True)
    img.crop((r.left - ox, r.top - oy, r.right - ox, r.bottom - oy)).save(caminho)
    return caminho
