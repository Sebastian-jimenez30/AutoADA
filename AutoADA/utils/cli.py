# utils/cli.py
import sys, os

def _project_root() -> str:
    return os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))

def main_entry_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.join(_project_root(), "main.py")

def build_cmd(module: str, *args: str) -> list[str]:
    """
    Devuelve argv correcto:
      - dev:  [python, -u, -m, module, *args]   <-- corre el módulo directo (stdout fluye)
      - exe:  [<exe>, --run, module, *args]     <-- usa el dispatcher del exe
    """
    entry = main_entry_path()
    if getattr(sys, "frozen", False):
        # En ejecutable seguimos usando el dispatcher del exe
        return [entry, "--run", module, *args]
    else:
        # MUY IMPORTANTE: -u para stdout sin buffering
        return [sys.executable, "-u", "-m", module, *args]
