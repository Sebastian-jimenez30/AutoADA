# autoada_web/utils/cli.py
import sys

def build_cmd(module: str, args=None):
    """
    Arma el comando para ejecutar un script Python como módulo.
    Ejemplo: python -m scripts.importar_all itco1sca01 ITCO sca,hsh,ods
    """
    if args is None:
        args = []
    return [sys.executable, "-u", "-m", module] + list(map(str, args))
