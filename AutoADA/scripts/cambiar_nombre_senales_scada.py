"""Wrapper sin acentos para scripts.cambiar_nombre_señales_scada."""
from __future__ import annotations

import runpy
import sys

_TARGET_MODULE = "scripts.cambiar_nombre_se\u00f1ales_scada"


def main() -> None:
    runpy.run_module(_TARGET_MODULE, run_name="__main__")


if __name__ == "__main__":
    main()

