from __future__ import annotations

import os
import sys
from typing import List, Tuple

from tkinter import messagebox

from utils.cli import build_cmd
from utils.data_checks import find_mode_data_ready
from ui.components.success_dialog import show_success_with_open

__all__ = [
    "messagebox",
    "build_cmd",
    "find_mode_data_ready",
    "show_success_with_open",
    "_runtime_root",
    "_validar_keys",
]


def _runtime_root() -> str:
    """Ubicación raíz para OUT/DB/LOG al ejecutar en modo congelado o desarrollo."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def _validar_keys(cadena: str) -> Tuple[List[str], List[str]]:
    """Divide la cadena y separa keys válidas (comodín o formato 12345.67) de las inválidas."""
    keys = [k.strip().upper() for k in cadena.split(",")]
    validas, invalidas = [], []
    for key in keys:
        if "%" in key:
            validas.append(key)
        elif len(key) == 8 and key[:5].isdigit() and key[6:].isdigit():
            validas.append(key)
        else:
            invalidas.append(key)
    return validas, invalidas

