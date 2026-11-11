import json, os, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def caminho_config():
    """Config do usuário (Documentos\\ConciliadorERP\\config.json) tem prioridade sobre a que vem no pacote."""
    pessoal = pasta_dados() / "config.json"
    if not pessoal.exists() and (RAIZ / "config.json").exists():
        import shutil
        shutil.copyfile(RAIZ / "config.json", pessoal)  # 1ª execução: cria a config editável do usuário
        print(f"Config pessoal criada: {pessoal} (edite para outras empresas/planilhas)")
    return pessoal if pessoal.exists() else RAIZ / "config.json"


def carregar(caminho=None):
    p = Path(caminho) if caminho else caminho_config()
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def empresa(cfg, nome):
    emp = cfg["empresas"].get(nome)
    if not emp:
        raise SystemExit(f"Empresa '{nome}' não existe no config.json. Opções: {', '.join(cfg['empresas'])}")
    return emp


def pasta_dados():
    """Pasta local (fora do OneDrive) onde ficam capturas, extrações e relatórios."""
    base = Path(os.environ.get("CONCILIADOR_DADOS") or (Path.home() / "Documents" / "ConciliadorERP"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def nova_execucao(empresa_nome):
    d = pasta_dados() / empresa_nome / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    (d / "capturas").mkdir(parents=True, exist_ok=True)
    return d


def ultima_execucao(empresa_nome):
    base = pasta_dados() / empresa_nome
    runs = sorted([p for p in base.glob("*") if p.is_dir()]) if base.exists() else []
    if not runs:
        raise SystemExit(f"Nenhuma coleta encontrada para '{empresa_nome}'. Rode 'coletar' primeiro.")
    return runs[-1]
