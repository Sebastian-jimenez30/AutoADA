# utils/data_checks.py
import os
from typing import Tuple, Dict, Iterable
from utils.paths import output_root


def _dir_has_exts(path: str, exts: Iterable[str], recursive: bool = False) -> bool:
    """True si hay al menos un archivo con alguna de las extensiones dadas."""
    if not os.path.isdir(path):
        return False
    exts = tuple(e if e.startswith(".") else f".{e}" for e in (x.lower() for x in exts))
    if recursive:
        for _, _, files in os.walk(path):
            if any(f.lower().endswith(exts) for f in files):
                return True
        return False
    return any(name.lower().endswith(exts) for name in os.listdir(path))


def _out_candidates(base_dir: str | None, empresa: str) -> list[str]:
    """Devuelve las dos posibles raíces de OUT: la del ejecutable y la del run local."""
    candidates = []
    if base_dir:
        candidates.append(os.path.join(base_dir, "out", empresa))          # run local
    candidates.append(os.path.join(output_root(), "out", empresa))         # ejecutable
    # de-duplicar manteniendo orden
    seen, out = set(), []
    for p in candidates:
        if p not in seen:
            out.append(p); seen.add(p)
    return out


def find_mode_data_ready(base_dir: str | None, empresa: str) -> tuple[bool, dict]:
    """
    Datos mínimos para Buscar Key/Keys:
      - SCADA: cualquier .csv
      - HSH:   groups.csv y lookup_table.csv
      - ODSTXT: cualquier .txt  (también aceptamos .csv por compatibilidad)
    Se considera OK si *cualquiera* de las dos raíces (exe o run local) cumple.
    """
    outs = _out_candidates(base_dir, empresa)

    out_ok   = any(os.path.isdir(p) for p in outs)
    scada_ok = any(_dir_has_exts(os.path.join(p, "SCADA"),  ["csv"])       for p in outs)
    hsh_ok   = any(
        os.path.isfile(os.path.join(p, "HSH", "groups.csv")) and
        os.path.isfile(os.path.join(p, "HSH", "lookup_table.csv"))
        for p in outs
    )
    ods_ok   = any(_dir_has_exts(os.path.join(p, "ODSTXT"), ["txt", "csv"]) for p in outs)

    details = {"OUT": out_ok, "SCADA": scada_ok, "HSH": hsh_ok, "ODSTXT": ods_ok}
    ok = scada_ok and hsh_ok and ods_ok
    return ok, details


def jobs_mode_data_ready(base_dir: str | None, empresa: str) -> bool:
    outs = _out_candidates(base_dir, empresa)
    return any(_dir_has_exts(os.path.join(p, "SCADA"), ["csv"]) for p in outs)


def unifilares_mode_data_ready(base_dir: str | None, empresa: str) -> bool:
    outs = _out_candidates(base_dir, empresa)
    # Unifilares consume ODSTXT → archivos .txt (aceptamos .csv por compatibilidad)
    return any(_dir_has_exts(os.path.join(p, "ODSTXT"), ["txt", "csv"]) for p in outs)
