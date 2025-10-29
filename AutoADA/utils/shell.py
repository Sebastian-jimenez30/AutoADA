# utils/shell.py
import os
import sys
import subprocess
from typing import Optional


def _exists(path: Optional[str]) -> bool:
    return bool(path) and os.path.exists(path)


def open_path(path: str) -> bool:
    """
    Abre un archivo o carpeta con la aplicación predeterminada del SO.
    - Windows: os.startfile
    - macOS:   open <path>
    - Linux:   xdg-open <path>
    Retorna True si el comando se lanzó sin excepciones.
    """
    if not _exists(path):
        return False

    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
            return True
        else:
            subprocess.run(["xdg-open", path], check=False)
            return True
    except Exception:
        return False


def open_in_file_manager(path: str, select: bool = False) -> bool:
    """
    Abre el explorador de archivos mostrando 'path'.
    - Si 'path' es un archivo y select=True:
        * Windows: explorer /select,"<path>"
        * macOS:   open -R "<path>"  (reveal)
        * Linux:   abre la carpeta contenedora
    - Si 'path' es carpeta o select=False:
        abre la carpeta (Windows/Mac/Linux).
    Retorna True si el comando se lanzó sin excepciones.
    """
    if not _exists(path):
        return False

    try:
        is_dir = os.path.isdir(path)
        if sys.platform.startswith("win"):
            if not is_dir and select:
                subprocess.run(["explorer", "/select,", os.path.normpath(path)], check=False)
                return True
            # Si es dir o no queremos seleccionar, abrir la carpeta
            folder = path if is_dir else os.path.dirname(path)
            os.startfile(folder)  # type: ignore[attr-defined]
            return True

        elif sys.platform == "darwin":
            if not is_dir and select:
                subprocess.run(["open", "-R", path], check=False)  # reveal
                return True
            folder = path if is_dir else os.path.dirname(path)
            subprocess.run(["open", folder], check=False)
            return True

        else:
            # Linux: no hay "reveal" estándar; abrir la carpeta contenedora
            folder = path if is_dir else os.path.dirname(path)
            subprocess.run(["xdg-open", folder], check=False)
            return True
    except Exception:
        return False


def reveal_path(path: str) -> bool:
    """
    Atajo: intenta “revelar” el archivo en el explorador (si el SO lo soporta).
    """
    return open_in_file_manager(path, select=True)
