# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import shutil
import fnmatch
from typing import Dict, Any, Iterable, Optional, Tuple, List

from utils.paths import input_root, output_root

# ---- Logger + helpers del proyecto (cargas tolerantes) ----
try:
    from scripts import _Logger as Logger
    from scripts.functions import sshserver
except Exception:
    try:
        import _Logger as Logger
        from functions import sshserver
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger
        from functions import sshserver


# -------------------------
# Logging helpers (azucar)
# -------------------------
def log_all(level: str, msg: str, logger_console, logger):
    Logger.write_log().log_all(level, msg, logger_console, logger)

def log_files(level: str, msg: str, logger):
    Logger.write_log().log_files(level, msg, logger)

# -------------------------
# Config loader + deep merge
# -------------------------
def load_profiles_config() -> Dict[str, Any]:
    """
    Lee config/import_profiles.json. Si no existe, levanta.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base_dir, "config", "import_profiles.json")
    if not os.path.isfile(p):
        raise FileNotFoundError(f"No existe config/import_profiles.json en {p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge recursivo (src pisa dst). No modifica originales.
    """
    out = dict(dst or {})
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def resolve_usecase(config: Dict[str, Any], usecase: Optional[str]) -> Dict[str, Any]:
    """
    Devuelve un dict con las secciones scada/hsh/ods ya mergeadas con defaults.
    """
    defaults = config.get("defaults", {})
    uc = (config.get("usecases", {}) or {}).get(usecase or "", {}) if usecase else {}
    resolved = {}
    for section in ("scada", "hsh", "ods"):
        resolved[section] = deep_merge(defaults.get(section, {}), uc.get(section, {}))
    return resolved

# -------------------------
# Destinos (carpetas)
# -------------------------
def make_target_dir(empresa: str, tipo: str) -> str:
    """
    Crea y devuelve destino: input_root()/db/<empresa>/<TIPO>
    """
    topath = os.path.join(input_root(), "db", empresa, tipo.upper())
    os.makedirs(topath, exist_ok=True)
    return topath

def reset_dir(path: str, logger_console=None, logger=None):
    """
    Limpia la carpeta destino (si existe) y la recrea.
    """
    try:
        if os.path.exists(path) and os.listdir(path):
            if logger_console and logger:
                log_all('info', f'Reiniciando carpeta {path}', logger_console, logger)
            shutil.rmtree(path)
            time.sleep(0.5)
        os.makedirs(path, exist_ok=True)
        if logger_console and logger:
            log_all('info', f'Carpeta lista {path}', logger_console, logger)
    except PermissionError as e:
        if logger_console and logger:
            log_all('error', f'Fallo al reiniciar carpeta {path}: {e}', logger_console, logger)
        raise
    except Exception as e:
        if logger_console and logger:
            log_all('error', f'Error inesperado al reiniciar carpeta {path}: {e}', logger_console, logger)
        raise

# -------------------------
# SFTP transfer generico
# -------------------------
def sftp_transfer(client, from_path: str, to_path: str,
                  files: Optional[Iterable[str]] = None,
                  pattern: Optional[str] = None,
                  logger_console=None, logger=None) -> Tuple[int, int, List[str]]:
    """
    Transfiere por SFTP desde from_path a to_path.
    - files: lista blanca exacta (si se provee, ignora pattern)
    - pattern: glob / substring para filtrar (e.g. ".ODS")
    Devuelve: (transferidos, total, lista_nombres)
    """
    sftp = client.open_sftp()
    if logger_console and logger:
        log_all('info', f'Listando SFTP {from_path}', logger_console, logger)
    names = sftp.listdir(path=from_path)
    # Filtrado
    if files and files != "ALL":
        names = [n for n in names if n in set(files)]
    elif pattern:
        names = [n for n in names if fnmatch.fnmatch(n, pattern) or (pattern in n)]
    # Log recorrido
    for n in names:
        if logger:
            log_files('debug', f'Ruta leida {from_path}/{n}', logger)
    if logger_console and logger:
        log_all('info', f'Listado SFTP listo {from_path}', logger_console, logger)

    transferred = 0
    total = len(names)
    if logger_console and logger:
        log_all('info', f'Inicio transferencia {from_path} -> {to_path}', logger_console, logger)
    for n in names:
        try:
            sftp.get(os.path.join(from_path, n), os.path.join(to_path, n))
            if logger:
                log_files('debug', f'Archivo transferido {n}', logger)
            transferred += 1
        except Exception:
            if logger_console and logger:
                log_all('warning', f'Fallo transferencia {n}', logger_console, logger)

    return transferred, total, names

# -------------------------
# Flex (empresa relacionada)
# -------------------------
_RELATED_COMPANY = {
    "REPS": "REPP",
    "REPP": "REPS",
    "ITCO": "TRA",
    "TRA": "ITCO",
}

_COMPANY_PREFIXES = {
    "REPS": ("rep1",),
    "REPP": ("rep2",),
    "ITCO": ("itco1", "itco2"),
    "TRA": ("tra1", "tra2"),
}


def related_company(empresa: str) -> Optional[str]:
    return _RELATED_COMPANY.get(empresa.upper())


def company_prefixes(empresa: str) -> Tuple[str, ...]:
    return _COMPANY_PREFIXES.get(empresa.upper(), tuple())


def _split_prefix(server: str, prefixes: Tuple[str, ...]) -> Tuple[Optional[str], str]:
    for prefix in prefixes:
        if prefix and prefix in server:
            suffix = server.split(prefix, 1)[1]
            return prefix, suffix
    return None, server


def replace_server_prefix(server: str, empresa: str) -> str:
    """Mantiene compatibilidad devolviendo el primer candidato relacionado."""
    candidates = related_server_candidates(server, empresa)
    return candidates[0] if candidates else server


def related_server_candidates(server: str, empresa: str) -> List[str]:
    rel = related_company(empresa)
    if not rel:
        return []

    src_prefixes = company_prefixes(empresa)
    dest_prefixes = company_prefixes(rel)

    prefix, suffix = _split_prefix(server, src_prefixes)
    candidates: List[str] = []
    for dest in dest_prefixes:
        if not dest:
            continue
        if prefix:
            candidate = dest + suffix
        else:
            candidate = dest
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates

