# utils/last_update.py
import os
import time
from datetime import datetime, timedelta
from utils.paths import output_root   # << nuevo

DEFAULT_FMT = "%Y-%m-%d %H:%M"


def _max_mtime_in(path: str) -> float | None:
    """Devuelve el mtime más reciente (en epoch) dentro de 'path' (recursivo).
    Si no hay archivos, intenta el mtime del directorio. Si no existe, None.
    """
    try:
        if not os.path.exists(path):
            return None
        latest = None
        # Recorrer archivos
        for root, _dirs, files in os.walk(path):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    mt = os.path.getmtime(fpath)
                    if latest is None or mt > latest:
                        latest = mt
                except OSError:
                    pass
        # Fallback: mtime del directorio
        try:
            dmt = os.path.getmtime(path)
            if latest is None or dmt > latest:
                latest = dmt
        except OSError:
            pass
        return latest
    except Exception:
        return None


def _humanize_delta(dt: datetime, now: datetime) -> str:
    """Devuelve una cadena tipo 'hace 2 h 15 m' / 'hace 3 d', etc."""
    delta: timedelta = now - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        secs = 0
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d >= 1:
        return f"hace {d} d"
    if h >= 1:
        return f"hace {h} h {m} m"
    if m >= 1:
        return f"hace {m} m"
    return "hace unos segundos"


def _out_candidates(base_dir: str | None, empresa: str) -> list[str]:
    """Posibles OUT: el del run local y el del ejecutable (PyInstaller)."""
    candidates: list[str] = []
    # run local (cuando ejecutas python main.py)
    local_root = os.path.join(base_dir or os.getcwd(), "out", empresa)
    candidates.append(local_root)
    # ejecutable (al lado del .exe)
    exe_root = os.path.join(output_root(), "out", empresa)
    if exe_root not in candidates:
        candidates.append(exe_root)
    return candidates


def last_update_for(base_dir: str, empresa: str, subfolders: list[str]) -> tuple[str | None, float | None]:
    """Busca el último mtime entre las carpetas dadas bajo out/<empresa>/ en
    **ambos** orígenes (run local y ejecutable).
    Retorna (nombre_carpeta, epoch_mtime) o (None, None) si no hay nada.
    """
    best_folder: str | None = None
    best_mtime: float | None = None

    for out_dir in _out_candidates(base_dir, empresa):
        for sf in subfolders:
            p = os.path.join(out_dir, sf)
            mt = _max_mtime_in(p)
            if mt is not None and (best_mtime is None or mt > best_mtime):
                best_folder, best_mtime = sf, mt

    return best_folder, best_mtime


def last_update_text(base_dir: str, empresa: str, subfolders: list[str], fmt: str = DEFAULT_FMT) -> str:
    """Texto listo para UI: 'Última actualización: 2025-09-03 12:34 (hace 2 h 15 m) – SCADA'
    Si no hay datos, devuelve 'Última actualización: —'
    """
    folder, mt = last_update_for(base_dir, empresa, subfolders)
    if folder is None or mt is None:
        return "Última actualización: —"
    dt = datetime.fromtimestamp(mt)
    now = datetime.now()
    return f"Última actualización: {dt.strftime(fmt)} ({_humanize_delta(dt, now)}) – {folder}"
