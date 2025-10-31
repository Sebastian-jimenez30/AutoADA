from __future__ import annotations

from utils.cli import build_cmd

def _mods():
    return {
        "importar": "scripts.importar_all",
        "convertir": "scripts.Convertir_all",
        "validar": "scripts.Validacion_unifilares",
    }


def _ui(app, fn):
    try:
        app.ventana.after(0, fn)
    except Exception:
        pass


def _console_factory(app):
    def _console(line: str, tag: str = "info"):
        if getattr(app, "console", None):
            _ui(app, lambda: app.console.write(line, tag))
    return _console


def _on_progress_factory(app, prefix: str = ""):
    console = _console_factory(app)

    def _on_progress(line: str):
        line = (line or "").strip()
        if not line:
            return
        lower = line.lower()
        tag = "info"
        if "error" in lower or "failed" in lower or "traceback" in lower:
            tag = "error"
            _ui(app, lambda: app.error_status(f"{prefix}{line}"))
        elif "warn" in lower or "warning" in lower:
            tag = "warn"
        elif "%" in line or "..." in line or "step" in lower or "progreso" in lower:
            _ui(app, lambda: app.set_status(f"{prefix}{line}"))
        console(f"{prefix}{line}", tag)

    return _on_progress


__all__ = [
    "_mods",
    "_ui",
    "_console_factory",
    "_on_progress_factory",
    "build_cmd",
]
