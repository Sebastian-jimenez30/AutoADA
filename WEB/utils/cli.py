# WEB/utils/cli.py
import sys

def build_cmd(module: str, args=None):
    """
    Arma el comando para ejecutar un script Python como módulo.
    Ejemplo: python -m scripts.importar_all itco1sca01 ITCO sca,hsh,ods --usecase buscar_keys
    """
    if args is None:
        args = []
    # Asegurar que todos los elementos sean strings y aplanar
    cmd = [sys.executable, "-u", "-m", module] + list(map(str, args))
    return cmd
