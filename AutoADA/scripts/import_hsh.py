# -*- coding: utf-8 -*-
import os
import sys
from typing import Optional
from bson import json_util

from utils.paths import input_root

# === IMPORTS TOLERANTES A PAQUETE/DATA ===
# import_base
try:
    from scripts.import_base import (
        load_profiles_config, resolve_usecase, make_target_dir, reset_dir,
        log_all, log_files, replace_server_prefix, related_company,
        related_server_candidates
    )
except Exception:
    try:
        from import_base import (
        load_profiles_config, resolve_usecase, make_target_dir, reset_dir,
        log_all, log_files, replace_server_prefix, related_company,
        related_server_candidates
        )
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        from import_base import (
        load_profiles_config, resolve_usecase, make_target_dir, reset_dir,
        log_all, log_files, replace_server_prefix, related_company,
        related_server_candidates
        )

# Logger + functions
try:
    from scripts import _Logger as Logger
    from scripts.functions import conexion_hsh
except Exception:
    try:
        import _Logger as Logger
        from functions import conexion_hsh
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger
        from functions import conexion_hsh



def _target_db(empresa: str) -> str:
    if   empresa == "REPS": return "PI_REPS"
    elif empresa == "REPP": return "PI_REPP"
    elif empresa == "ITCO": return "PI_ITCO"
    elif empresa == "TRA":  return "PI_TRA"
    return empresa


def run(server: str, empresa: str, usecase: Optional[str], flex: bool,
        logger, logger_console):
    cfg = load_profiles_config()
    resolved = resolve_usecase(cfg, usecase)
    hh = resolved.get("hsh", {}) or {}
    if not hh.get("enabled", False):
        log_all('info', f'HSH deshabilitado para caso {usecase}', logger_console, logger)
        return

    log_all('info', f'Inicia importacion HSH {empresa}', logger_console, logger)
    topath = make_target_dir(empresa, "HSH")
    reset_dir(topath, logger_console, logger)

    collections = hh.get("collections", []) or []
    filters = hh.get("filters", {}) or {}

    try:
        client, tunnel, cert_path, key_path = conexion_hsh(empresa, server, logger, logger_console)
        db = client[_target_db(empresa)]

        for name in collections:
            query = filters.get(name, {}) if isinstance(filters, dict) else {}
            path = os.path.join(topath, f"{name}.json")
            count = db[name].count_documents(query)
            if count == 0:
                log_all('info', f"Coleccion {name} vacia con filtro", logger_console, logger)
                with open(path, "w", encoding="utf-8") as f:
                    f.write("")
                continue
            with open(path, "w", encoding="utf-8") as f:
                for doc in db[name].find(query):
                    f.write(json_util.dumps(doc, ensure_ascii=False) + "\n")
            log_all('info', f"Guardado {name}.json ({count} docs)", logger_console, logger)

        # Cierres/limpieza
        tunnel.stop()
        for p in (cert_path, key_path):
            if p and os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

        log_all('info', f"Importacion HSH lista para {empresa}", logger_console, logger)

    except Exception as e:
        logger_console.exception(f"Error importacion HSH para {empresa}", exc_info=False)
        logger.exception(e, exc_info=True)

    # Flex
    if flex:
        rel = related_company(empresa)
        if rel:
            candidates = related_server_candidates(server, empresa) or [replace_server_prefix(server, empresa)]
            last_error = None
            for server_rel in candidates:
                try:
                    log_all('info', f'Importacion HSH flex {rel} via {server_rel}', logger_console, logger)
                    run(server_rel, rel, usecase, False, logger, logger_console)
                    break
                except Exception as exc:
                    last_error = exc
                    logger_console.exception(f"Error importacion HSH flex para {rel} usando {server_rel}", exc_info=False)
                    logger.exception(exc, exc_info=True)
                    continue
            else:
                if last_error:
                    log_all('error', f'Importacion HSH flex {rel} fallo en todos los candidatos', logger_console, logger)
