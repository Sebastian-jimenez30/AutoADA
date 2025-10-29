# autoada_web/controllers/importar_controller.py
import subprocess
from utils.cli import build_cmd
import os

# Ruta del proyecto AutoADA (un nivel arriba)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOADA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AutoADA"))



def ejecutar_importar(empresa: str):
    """
    Lógica simple para ejecutar el script importar_all con la empresa indicada.
    Más adelante añadiremos vault, seguridad, y logs en vivo.
    """
    # Comando del script (modo desarrollo)
    cmd = build_cmd("scripts.importar_all", ["itco1sca01", empresa, "sca,hsh,ods", "--usecase", "buscar_keys"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=AUTOADA_DIR)
        output = result.stdout + "\n" + result.stderr
        return f"Comando ejecutado: {' '.join(cmd)}\n\nSalida:\n{output}"
    except Exception as e:
        return f"Error ejecutando importar_all:\n{e}"
