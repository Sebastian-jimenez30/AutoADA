import subprocess, os
from utils.cli import build_cmd
from services.vault_service import VaultService

def ejecutar_importar(empresa: str):
    """Ejecuta el script importar_all con las variables del vault cargadas."""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    AUTOADA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AutoADA"))

    # Comando correcto
    cmd = build_cmd(
        "scripts.importar_all",
        ["itco1sca01", empresa, "sca,hsh,ods", "--usecase", "buscar_keys"]
    )

    # Cargar variables del vault
    env = VaultService.build_env()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=AUTOADA_DIR, env=env)
        output = result.stdout + "\n" + result.stderr
        return f"Comando ejecutado: {' '.join(cmd)}\n\nSalida:\n{output}"
    except Exception as e:
        return f"Error ejecutando importar_all:\n{e}"
