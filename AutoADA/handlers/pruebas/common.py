from __future__ import annotations

import os
import re
import sys

from utils.cli import build_cmd
from utils.paths import output_root, project_root
from ui.components.success_dialog import show_success_with_open

_RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_TIME_MS = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\.\d{3}$")


def _valid_date(s: str) -> bool:
    return bool(_RE_DATE.match((s or '').strip()))


def _valid_time_ms(s: str) -> bool:
    return bool(_RE_TIME_MS.match((s or '').strip()))


def _runtime_root() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def _mods():
    return {
        'ioa_v1': 'scripts.itcosas_v1_ioa',
        'soe_local_v1': 'scripts.itcosas_v1_soe_local',
        'soe_monarch_v1': 'scripts.pyp_soe_monarch',
        'checklist_v1': 'scripts.pyp_checklist',
        'his_soe': 'scripts.import_his_soe',
        'soe_local_v2': 'scripts.itcosas_v2_soe_local',
        'soe_monarch_v2': 'scripts.itcosas_v2_soe_monarch',
        'checklist_v2': 'scripts.itcosas_v2_checklist',
    }


def _ui(app, fn):
    try:
        app.ventana.after(0, fn)
    except Exception:
        pass


def _console_factory(app):
    def _console(line: str, tag: str = 'info'):
        if getattr(app, 'console', None):
            _ui(app, lambda: app.console.write(line, tag))
    return _console


def _on_progress_factory(app, prefix: str = ''):
    console = _console_factory(app)

    def _on_progress(line: str):
        line = (line or '').strip()
        if not line:
            return
        lower = line.lower()
        tag = 'info'
        if 'error' in lower or 'failed' in lower or 'traceback' in lower:
            tag = 'error'
            _ui(app, lambda: app.error_status(f"{prefix}{line}"))
        elif 'warn' in lower or 'warning' in lower:
            tag = 'warn'
        elif '%' in line or '...' in line or 'step' in lower or 'progreso' in lower or 'consultando' in lower:
            _ui(app, lambda: app.set_status(f"{prefix}{line}"))
        console(f"{prefix}{line}", tag)

    return _on_progress


__all__ = [
    '_valid_date',
    '_valid_time_ms',
    '_runtime_root',
    '_mods',
    '_ui',
    '_console_factory',
    '_on_progress_factory',
    'build_cmd',
    'output_root',
    'project_root',
    'show_success_with_open',
]


