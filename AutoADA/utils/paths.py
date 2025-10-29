# utils/paths.py
import os
import sys

# ===========================
# Detección de entorno
# ===========================
def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundle_root() -> str:
    """
    Raíz de recursos de solo-lectura (PyInstaller):
      - onefile: sys._MEIPASS
      - dev: carpeta del archivo actual
    """
    if is_frozen():
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def exec_dir() -> str:
    """
    Carpeta donde vive el ejecutable (onefile) o el script (dev).
    ÚSALA para todo lo que deba quedar “al lado del .exe”.
    """
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def runtime_root() -> str:
    """
    Raíz de trabajo en tiempo de ejecución:
      - frozen: carpeta del .exe
      - dev: CWD
    """
    if is_frozen():
        return exec_dir()
    return os.getcwd()

# ===========================
# Raíces de trabajo separadas
# ===========================
def appdata_root(app_name: str = "ADA-DOT") -> str:
    """
    Carpeta de trabajo de ESCRITURA para **staging/temporales** (db, tls…).
    En Windows usa %LOCALAPPDATA% (o %TEMP% como fallback).
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or exec_dir()
    path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path


def input_root(app_name: str = "ADA-DOT") -> str:
    """
    Raíz para **entradas temporales** creadas por importar_all (db/, tls/…).
    Siempre en AppData para no ensuciar la carpeta del .exe.
    """
    root = appdata_root(app_name)
    for d in ("db", "tls"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    return root


def output_root(app_name: str = "ADA-DOT") -> str:
    """
    Raíz para **salidas visibles** (out/, log/) al lado del .exe.
    Esto es lo que quieres verificar/consumir desde la UI.
    """
    root = runtime_root()
    for d in ("out", "log"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    return root

# ===========================
# Helpers de alto nivel
# ===========================
def out_dir_for(empresa: str, app_name: str = "ADA-DOT") -> str:
    """
    out/<empresa> bajo la carpeta del .exe.
    """
    root = output_root(app_name)
    p = os.path.join(root, "out", empresa)
    os.makedirs(p, exist_ok=True)
    return p


def db_dir_for(empresa: str, app_name: str = "ADA-DOT") -> str:
    """
    db/<empresa> en AppData (staging de import).
    """
    root = input_root(app_name)
    p = os.path.join(root, "db", empresa)
    os.makedirs(p, exist_ok=True)
    return p

def ensure_workdirs(app_name: str = "ADA-DOT") -> str:
    """
    Mantener compatibilidad: crea db/ en AppData y out/log junto al .exe.
    Devuelve SIEMPRE la raíz de salidas (carpeta del .exe).
    """
    input_root(app_name)   # garantiza db/ y tls/ en AppData
    return output_root(app_name)  # garantiza out/ y log/ junto al .exe

def project_root() -> str:
    """
    Devuelve la raíz del proyecto:
      - frozen: carpeta del .exe (junto a config/, assets/, etc.)
      - dev:    carpeta padre de utils/  (donde viven config/, assets/)
    """
    if is_frozen():
        return exec_dir()
    # utils/paths.py -> subimos un nivel
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _resolve_data_path(subdir: str, *parts: str) -> str:
    """Resolve bundled resource paths while allowing overrides next to the executable."""
    relative = os.path.join(subdir, *parts)
    if is_frozen():
        candidates = [
            os.path.join(exec_dir(), relative),
            os.path.join(bundle_root(), relative),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return candidates[0]
    return os.path.join(project_root(), relative)

def config_path(name: str) -> str:
    """Ruta a un archivo dentro de config/ en la ra�z del proyecto."""
    return _resolve_data_path("config", name)

def asset_path(*parts: str) -> str:
    """Ruta a un asset dentro de assets/ en la ra�z del proyecto."""
    return _resolve_data_path("assets", *parts)
