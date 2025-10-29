import argparse
import os
import sys
import glob
import json
import re
import subprocess
from typing import Dict, List, Optional

import pandas as pd
from io import StringIO
import concurrent.futures
import threading
from utils.paths import output_root, appdata_root, config_path
try:
    from scripts import _Logger as Logger
    from scripts.Convertir_Unifilares import conver_unifilares_to_csv
except Exception:
    try:
        import _Logger as Logger
        from Convertir_Unifilares import conver_unifilares_to_csv
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger
        from Convertir_Unifilares import conver_unifilares_to_csv


# =========================================================
# Helpers de rutas
# =========================================================
def _DB(*parts) -> str:
    """Raiz de datos importados (AppData/db/...)."""
    base = appdata_root("ADA-DOT")
    p = os.path.join(base, "db", *parts)
    os.makedirs(p, exist_ok=True)
    return p


def _OUT(*parts) -> str:
    """Raiz de salidas visibles (junto al .exe -> out/...)."""
    base = output_root("ADA-DOT")  # crea out/ y log/ si no existen
    p = os.path.join(base, *parts)
    os.makedirs(p, exist_ok=True)
    return p


# =========================================================
# CLI
# =========================================================
def get_args():
    parser = argparse.ArgumentParser(description='Script to convert SCADA and/or Unifilar files.')
    parser.add_argument('empresa', type=str, help='Nombre de la empresa')
    parser.add_argument(
        'modo',
        type=str,
        choices=['Buscar_keys', 'Validar_HSH', 'jobs', 'unifilares'],
        help='Conversion mode (Buscar_keys, Validar_HSH, jobs, unifilares)'
    )
    # NUEVO: conversion granular para que los handlers disparen por componente
    parser.add_argument(
        '--only',
        type=str,
        default=None,
        help='Components to convert (comma or space separated): sca, hsh, ods, ods_csv'
    )
    return parser.parse_args()


# =========================================================
# Concurrencia y logging seguro (opcional)
# =========================================================
_LOG_LOCK = threading.Lock()


def safe_log(callable_):
    """Serializa escrituras criticas al logger para evitar lineas mezcladas."""
    try:
        with _LOG_LOCK:
            callable_()
    except Exception:
        pass

def _parse_only(val):
    """
    Normaliza el parametro --only a una lista en {'sca','hsh','ods','ods_csv'}.
    Acepta valores separados por coma y/o espacios.
    """
    if not val:
        return None
    if isinstance(val, str):
        tokens = re.split(r"[,\s]+", val.strip())
    else:
        tokens = list(val)
    valid = {"sca", "hsh", "ods", "ods_csv"}
    items = [t for t in tokens if t in valid]
    return items or None



def _run_parallel(tasks, logger, logger_console, titulo="Parallel tasks", max_workers=None):
    """
    Ejecuta tareas en paralelo y espera por todas.
    - tasks: lista de tuplas (nombre, callable_sin_args)
    Retorna: dict {nombre: rc}, donde rc=0 si OK, rc=1 si fallo.
    """
    if max_workers is None:
        max_workers = min(4, max(1, len(tasks)))

    safe_log(lambda: Logger.write_log().log_all('info', f'[{titulo}] inicia {len(tasks)} tareas', logger_console, logger))
    results = {}

    def _wrap(name, fn):
        fn()        # Si falla lanza excepcion y se captura abajo
        return 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_map = {ex.submit(_wrap, name, fn): name for name, fn in tasks}
        for fut in concurrent.futures.as_completed(future_map):
            name = future_map[fut]
            try:
                fut.result()
                results[name] = 0
                safe_log(lambda: Logger.write_log().log_all('info', f'[{titulo}] {name} listo', logger_console, logger))
            except Exception as e:
                results[name] = 1
                safe_log(lambda: Logger.write_log().log_all('error', f'[{titulo}] {name} error: {e}', logger_console, logger))
                logger.exception(e, exc_info=True)

    safe_log(lambda: Logger.write_log().log_all('info', f'[{titulo}] listo', logger_console, logger))
    return results


# =========================================================
# SCADA
# =========================================================


def _extract_db_label(raw_lines):
    db_name = None
    table_name = None
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith('*'):
            continue
        tokens = re.split(r'\s+', stripped)
        if db_name is None and len(tokens) >= 2:
            maybe_db = tokens[1]
            if maybe_db.lower().endswith('.db'):
                maybe_db = maybe_db[:-3]
            db_name = maybe_db.replace('_', ' ')
            continue
        first_token = tokens[0].lstrip('#').lower() if tokens else ''
        if first_token == 'record':
            continue
        if table_name is None and len(tokens) >= 2:
            table_name = tokens[1].replace('_', ' ')
            break
    def _fmt(value):
        return re.sub(r'\s+', ' ', value).strip().upper() if value else None
    db_fmt = _fmt(db_name)
    table_fmt = _fmt(table_name)
    if db_fmt and table_fmt:
        return f"{db_fmt} {table_fmt}"
    return db_fmt or table_fmt


def convertir_scada(empresa, logger, logger_console):
    # Entradas: AppData/db/<empresa>/SCADA  |  Salidas: <exe>/out/<empresa>/SCADA
    base_dir = _DB(empresa, 'SCADA')
    if not os.path.exists(base_dir):
        msg = f"No existe la carpeta: {base_dir}"
        Logger.write_log().log_all('error', msg, logger_console, logger)
        raise FileNotFoundError(msg)

    output_dir = _OUT('out', empresa, 'SCADA')

    dat_files = glob.glob(os.path.join(base_dir, '*.dat'))
    if not dat_files:
        msg = 'No .dat files found in SCADA folder.'
        Logger.write_log().log_all('error', msg, logger_console, logger)
        raise RuntimeError(msg)

    ok_count = 0
    db_labels = {}
    for dat_path in dat_files:
        dat_filename = os.path.basename(dat_path)
        try:
            with open(dat_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            label = _extract_db_label(lines)

            # El .dat suele tener metadatos en las 4 primeras lineas
            data_lines = lines[4:]
            header = data_lines[0].strip().split('\t')
            header[0] = ''
            data_lines[0] = '\t'.join(header) + '\n'

            df = pd.read_csv(StringIO(''.join(data_lines)), sep='\t', low_memory=False)
            df = df.reset_index(drop=True)

            if str(df.iloc[0, 0]).lower() == "record":
                df.iloc[0, 0] = "#record"
            else:
                Logger.write_log().log_all('warning', f"{dat_filename} no contiene 'record' en la primera celda", logger_console, logger)

            df.columns = df.columns[1:].tolist() + ['']
            df = df.iloc[:, :-1]
            df.columns.values[0] = "0.0"

            column_mapping = dict(zip(df.iloc[0], df.columns))
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)

            if 'ICaddress' in df.columns:
                def extraer_key(val):
                    if pd.isna(val):
                        return val
                    # Busca una secuencia de 8 letras y/o numeros seguidos
                    m = re.search(r'\b[a-zA-Z0-9]{8}\b', str(val))
                    return m.group(0) if m else val

                df['ICaddress'] = df['ICaddress'].apply(extraer_key)

            csv_filename = os.path.splitext(dat_filename)[0] + '.csv'
            df.to_csv(os.path.join(output_dir, csv_filename), index=False)

            json_filename = os.path.splitext(dat_filename)[0] + '.json'
            with open(os.path.join(output_dir, json_filename), 'w', encoding='utf-8') as f:
                json.dump(column_mapping, f, indent=4)

            key_base = os.path.splitext(dat_filename)[0]
            if label:
                db_labels[key_base] = label
            else:
                db_labels.setdefault(key_base, key_base.replace('_', ' ').upper())

            Logger.write_log().log_all('info', f'Convertido {dat_filename}', logger_console, logger)
            ok_count += 1
        except Exception as e:
            Logger.write_log().log_all('error', f"Error processing {dat_filename}: {e}", logger_console, logger)
            logger.exception(e, exc_info=True)

    if ok_count == 0:
        # Nada pudo convertirse
        raise RuntimeError('SCADA: no .dat files converted')

    if db_labels:
        try:
            target_path = config_path('db_names.json')
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as fh:
                json.dump(dict(sorted(db_labels.items())), fh, indent=2)
            Logger.write_log().log_all('info', f'DB names guardados en {target_path}', logger_console, logger)
        except Exception as e:
            Logger.write_log().log_all('warning', f'No se pudo escribir db_names.json: {e}', logger_console, logger)
            logger.exception(e, exc_info=True)

    Logger.write_log().log_all('info', 'Conversion SCADA lista', logger_console, logger)

# =========================================================
# Unifilares (DisplayConverter externo)
# =========================================================
def convertir_unifilares(empresa, logger, logger_console):
    """
    Convierte archivos ODS a TXT usando DisplayConverter.
    - Oculta la ventana de consola del proceso externo en Windows.
    - Valida entradas/salidas y da logs legibles (ASCII).
    """
    import os, subprocess

    # Entradas / salidas
    base_dir = _DB(empresa, 'ODS')                 # AppData\db\<EMPRESA>\ODS
    output_dir = _OUT('out', empresa, 'ODSTXT')    # <exe>\out\<EMPRESA>\ODSTXT

    # 0) Chequear que existan .ODS importados
    try:
        ods_files = [f for f in os.listdir(base_dir) if f.upper().endswith('.ODS')]
    except FileNotFoundError:
        ods_files = []
    if not ods_files:
        msg = f'No .ODS files found in {base_dir}.'
        Logger.write_log().log_all('error', msg, logger_console, logger)
        raise FileNotFoundError(msg)

    # 1) Definir ruta del ejecutable externo (AJUSTA si es necesario)
    exe = r"D:\monarchNET\bin\DisplayConverter.exe"
    if not os.path.isfile(exe):
        msg = f'No existe DisplayConverter en: {exe}'
        Logger.write_log().log_all('error', msg, logger_console, logger)
        raise FileNotFoundError(msg)

    # 2) Definir cwd y env para el proceso hijo
    exe_dir = os.path.dirname(exe)
    cwd = exe_dir
    env = os.environ.copy()
    env["PATH"] = exe_dir + os.pathsep + env.get("PATH", "")

    Logger.write_log().log_all(
        'info',
        f'Inicio de conversion de unifilares... ODS={len(ods_files)} base="{base_dir}" out="{output_dir}"',
        logger_console, logger
    )

    empresa_u = (empresa or "").upper()

    def _domain_candidates(emp: str) -> List[Optional[str]]:
        env_specific = os.environ.get(f"DISPLAYCONVERTER_DOMAIN_{emp}")
        env_generic = os.environ.get("DISPLAYCONVERTER_DOMAIN")
        mapping = {
            "ITCO": ["CC-ITCO", "CC-TRA"],
            "TRA": ["CC-ITCO", "CC-TRA"],
            "REPS": ["CC-REPS", "CC-REP", "REPS"],
            "REPP": ["CC-REPS", "CC-REP", "REPS"],
        }
        candidates: List[Optional[str]] = []
        if env_specific:
            candidates.append(env_specific.strip())
        if env_generic:
            candidates.append(env_generic.strip())
        candidates.extend(mapping.get(emp, []))
        candidates.extend([f"CC-{emp}", emp])
        candidates.append(None)  # intento sin dominio
        seen: set[str] = set()
        dedup: List[Optional[str]] = []
        for item in candidates:
            key = item or "__NONE__"
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item if item != "__NONE__" else None)
        return dedup

    base_cmd = [
        exe,
        "-sso",
        "-p", base_dir,
        "--toreport", "*",
        "-o", output_dir,
    ]

    # 4) Config para NO mostrar ventana (solo Windows)
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def _snapshot_txt() -> Dict[str, float]:
        snapshot: Dict[str, float] = {}
        try:
            for name in os.listdir(output_dir):
                if not name.lower().endswith(".txt"):
                    continue
                full_path = os.path.join(output_dir, name)
                try:
                    snapshot[name] = os.path.getmtime(full_path)
                except OSError:
                    snapshot[name] = 0.0
        except FileNotFoundError:
            return {}
        return snapshot

    existing_snapshot = _snapshot_txt()

    attempt_errors: List[str] = []
    generated_txt: List[str] = []

    for domain_opt in _domain_candidates(empresa_u):
        domain_tag = domain_opt.strip() if isinstance(domain_opt, str) else "<none>"
        cmd = list(base_cmd)
        if domain_opt:
            cmd[1:1] = ["--domain", domain_opt]

        try:
            resultado = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=creationflags,
                shell=False,
            )
        except Exception as exc:
            attempt_errors.append(f"domain={domain_tag} -> exception {exc}")
            continue

        if resultado.stdout:
            Logger.write_log().log_files('debug', f"DisplayConverter STDOUT (domain={domain_tag}):\n{resultado.stdout}", logger)
        if resultado.stderr:
            Logger.write_log().log_all('warning', f'Advertencia DisplayConverter stderr (domain={domain_tag}): {resultado.stderr}', logger_console, logger)

        if resultado.returncode not in (0, None):
            human = 'Proceso interrumpido (0xC000013A)' if resultado.returncode == 3221225786 else f'Codigo {resultado.returncode}'
            attempt_errors.append(f"domain={domain_tag} -> {human}")
            continue

        current_snapshot = _snapshot_txt()
        current_txt = set(current_snapshot.keys())
        new_or_updated = [
            name for name in current_txt
            if name not in existing_snapshot or current_snapshot.get(name, 0.0) > existing_snapshot.get(name, 0.0)
        ]

        if new_or_updated:
            generated_txt = sorted(current_txt)
            Logger.write_log().log_all(
                'info',
                f'Conversion unifilares lista (domain={domain_tag}) nuevos/actualizados={len(new_or_updated)}',
                logger_console,
                logger,
            )
            break
        elif current_txt:
            generated_txt = sorted(current_txt)
            Logger.write_log().log_all(
                'info',
                f'Conversion unifilares lista (domain={domain_tag}) sin archivos nuevos (se reutilizan existentes)',
                logger_console,
                logger,
            )
            break
        else:
            attempt_errors.append(f"domain={domain_tag} -> sin TXT generados")

    if not generated_txt:
        summary = "; ".join(attempt_errors) if attempt_errors else "sin detalles"
        msg = f'Sin TXT creados en {output_dir}. Revisar ODS y logs DisplayConverter. ({summary})'
        Logger.write_log().log_all('error', msg, logger_console, logger)
        raise RuntimeError(msg)

# =========================================================
# HSH
# =========================================================
def convertir_hsh(empresa, logger, logger_console):
    """
    Convierte los JSON de HSH (lookup_tables.json y groups.json) a CSV.
    Ahora:
      - Falla (lanza excepcion) si falta la carpeta/archivos de entrada.
      - Falla si algun CSV de salida queda vacio o no se genera.
      - Loguea detalles y tamanos de salida.
    """

    input_dir = _DB(empresa, 'HSH')               # AppData/db/<empresa>/HSH
    output_dir = _OUT('out', empresa, 'HSH')      # <exe>/out/<empresa>/HSH

    Logger.write_log().log_all('info', f'Inicia conversion HSH {empresa}', logger_console, logger)

    if not os.path.isdir(input_dir):
        msg = f"HSH input folder missing: {input_dir}"
        Logger.write_log().log_all('error', msg, logger_console, logger)
        raise FileNotFoundError(msg)

    def obtener_oid(valor):
        if isinstance(valor, dict) and '$oid' in valor:
            return valor['$oid']
        return '' if valor is None else str(valor)

    archivos = {
        'lookup_tables': {
            'json': os.path.join(input_dir, 'lookup_tables.json'),
            'csv':  os.path.join(output_dir, 'lookup_table.csv'),
        },
        'groups': {
            'json': os.path.join(input_dir, 'groups.json'),
            'csv':  os.path.join(output_dir, 'groups.csv'),
        }
    }

    # Validacion de existencia de JSON requeridos
    lookup_json = archivos['lookup_tables']['json']
    if not os.path.isfile(lookup_json):
        msg = f"Missing HSH JSON files: lookup_tables in {input_dir}"
        Logger.write_log().log_all('error', msg, logger_console, logger)
        raise FileNotFoundError(msg)
    groups_json_missing = not os.path.isfile(archivos['groups']['json'])
    if groups_json_missing:
        Logger.write_log().log_all(
            'warning',
            f"groups.json no encontrado en {input_dir}; se generara CSV vacio.",
            logger_console,
            logger,
        )

    stats = {}

    # Procesar lookup_tables.json
    try:
        Logger.write_log().log_all('info', 'Procesando lookup_tables.json', logger_console, logger)
        rows = []
        with open(archivos['lookup_tables']['json'], encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rows.append({
                    'Key': obj.get('key', ''),
                    'Value': obj.get('value', ''),
                    'id': obtener_oid(obj.get('_id'))
                })

        df_lookup = pd.DataFrame(rows)
        if df_lookup.empty:
            msg = "lookup_tables.json no produjo filas."
            Logger.write_log().log_all('error', msg, logger_console, logger)
            raise ValueError(msg)

        df_lookup.to_csv(archivos['lookup_tables']['csv'], index=False)
        Logger.write_log().log_all('info', f"Generated lookup_table.csv ({len(df_lookup)} rows)", logger_console, logger)
        stats['lookup_table'] = len(df_lookup)

    except Exception as e:
        Logger.write_log().log_all('error', f"Lookup_tables.json error: {e}", logger_console, logger)
        logger.exception(e, exc_info=True)
        raise

    # Procesar groups.json
    try:
        Logger.write_log().log_all('info', 'Procesando groups.json', logger_console, logger)
        rows = []
        if not groups_json_missing:
            with open(archivos['groups']['json'], encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)

                    cpid = obtener_oid(data.get('_id'))
                    uid = data.get('uid', '')
                    transform_id = data.get('transform_id', '')
                    points = data.get('points', []) or []

                    for p in points:
                        rows.append({
                            'CPID': cpid,
                            'UID': uid,
                            'Transform_id': transform_id,
                            'PointName': p.get('point_name', ''),
                            'IsAuthorized': (p.get('last_auth_request_time_us', 0) or 0) != 0,
                            'IsPointValid': (p.get('point_error_message', '') or '') == '',
                            'IsIgnored': bool(p.get('user_ignore', False)),
                            'LinkAttributeValue': p.get('link_attr_value', ''),
                            'PointErrorMessage': p.get('point_error_message', ''),
                            'TagCreationErrorMessage': p.get('tag_creation_error_message', ''),
                            'TagErrorMessages': p.get('tag_error_messages', '')
                        })

        df_groups = pd.DataFrame(rows)
        if df_groups.empty:
            Logger.write_log().log_all(
                'warning',
                'groups.json no produjo filas (sin puntos). Se generara CSV vacio.',
                logger_console,
                logger,
            )
        if df_groups.empty:
            df_groups = pd.DataFrame(columns=[
                'CPID', 'UID', 'Transform_id', 'PointName', 'IsAuthorized',
                'IsPointValid', 'IsIgnored', 'LinkAttributeValue',
                'PointErrorMessage', 'TagCreationErrorMessage', 'TagErrorMessages',
                'UID1', 'UID2', 'UID3'
            ])
        else:
            if 'UID' in df_groups.columns:
                uid_split = df_groups['UID'].astype(str).str.split('/', n=2, expand=True)
                for i, col in enumerate(['UID1', 'UID2', 'UID3']):
                    if i < uid_split.shape[1]:
                        df_groups[col] = uid_split.iloc[:, i]
                    else:
                        df_groups[col] = ''
            else:
                for col in ['UID1', 'UID2', 'UID3']:
                    df_groups[col] = ''

        df_groups.to_csv(archivos['groups']['csv'], index=False)
        Logger.write_log().log_all('info', f"Generated groups.csv ({len(df_groups)} rows)", logger_console, logger)
        stats['groups'] = len(df_groups)

    except Exception as e:
        Logger.write_log().log_all('error', f"Groups.json error: {e}", logger_console, logger)
        logger.exception(e, exc_info=True)
        raise

    # Verificacion final de salidas
    for nombre, info in archivos.items():
        csv_path = info['csv']
        if not os.path.isfile(csv_path) or os.path.getsize(csv_path) == 0:
            msg = f"No valid output for {nombre}: {csv_path}"
            Logger.write_log().log_all('error', msg, logger_console, logger)
            raise RuntimeError(msg)

    Logger.write_log().log_all(
        'info',
        f"HSH convert done. Rows => lookup_table: {stats.get('lookup_table', 0)}, groups: {stats.get('groups', 0)}",
        logger_console, logger
    )

# =========================================================
# Main
# =========================================================
def main():
    args = get_args()
    empresa = args.empresa
    modo = args.modo

    log_dir = _OUT('log')
    log_path = os.path.join(log_dir, 'convertir_datos.log')
    logger, logger_console = Logger.initlog(log_path)

    Logger.write_log().log_all('info', f'Inicia conversion {empresa} modo {modo}', logger_console, logger)

    only = _parse_only(args.only)
    if only:
        component_map = {
            "sca":     ("SCADA",      lambda: convertir_scada(empresa, logger, logger_console)),
            "hsh":     ("HSH",        lambda: convertir_hsh(empresa, logger, logger_console)),
            "ods":     ("UNIFILARES", lambda: convertir_unifilares(empresa, logger, logger_console)),
            # ods_csv no es paralelo; depende del resultado de 'ods' si tambien se pidio
        }

        parallel = [component_map[c] for c in only if c in ("sca", "hsh", "ods")]
        res = {}
        if parallel:
            res = _run_parallel(parallel, logger, logger_console, titulo=f"--only[{empresa}]")

        if "ods_csv" in only:
            # Si tambien se pidio 'ods' y fallo, no hacer el CSV
            if any(k == "UNIFILARES" and rc != 0 for k, rc in res.items()):
                safe_log(lambda: Logger.write_log().log_all('error', 'Unifilares fallo, omitir ODSTXT -> CSV', logger_console, logger))
            else:
                safe_log(lambda: Logger.write_log().log_all('info', 'Convirtiendo ODSTXT -> CSV', logger_console, logger))
                conver_unifilares_to_csv(empresa, logger, logger_console)

        Logger.write_log().log_all('info', 'Conversion granular lista', logger_console, logger)
        return

    # Relaciones para modos que requieren empresas relacionadas
    relaciones = {
        "REPS": ["REPS", "REPP"],
        "REPP": ["REPP", "REPS"],
        "ITCO": ["ITCO", "TRA"],
        "TRA":  ["TRA", "ITCO"]
    }

    if modo == 'Buscar_keys':
        # 1) Correr SCADA, HSH y UNIFILARES en paralelo
        tasks = [
            ("SCADA",      lambda: convertir_scada(empresa, logger, logger_console)),
            ("HSH",        lambda: convertir_hsh(empresa, logger, logger_console)),
            ("UNIFILARES", lambda: convertir_unifilares(empresa, logger, logger_console)),
        ]
        res = _run_parallel(tasks, logger, logger_console, titulo=f"Convertir_all[{empresa}]/Buscar_keys")

        # 2) ODSTXT -> CSV depende SOLO de que UNIFILARES haya salido OK
        if res.get("UNIFILARES", 1) == 0:
            safe_log(lambda: Logger.write_log().log_all('info', 'Convirtiendo ODSTXT -> CSV', logger_console, logger))
            conver_unifilares_to_csv(empresa, logger, logger_console)
        else:
            safe_log(lambda: Logger.write_log().log_all('error', 'Unifilares fallo, omitir ODSTXT -> CSV', logger_console, logger))

    elif modo == 'Validar_HSH':
        # Para cada empresa (principal y relacionada), correr SCADA y HSH en paralelo.
        empresas_a_convertir = relaciones.get(empresa, [empresa])

        def _convertir_por_empresa(emp):
            safe_log(lambda: Logger.write_log().log_all('info', f'Inicia conversion para {emp}', logger_console, logger))

            res_emp = _run_parallel(
                [
                    ("SCADA", lambda: convertir_scada(emp, logger, logger_console)),
                    ("HSH",   lambda: convertir_hsh(emp, logger, logger_console)),
                ],
                logger, logger_console, titulo=f"Validar_HSH[{emp}]"
            )
            # Si alguna subtarea fallo, hacemos fallar la tarea externa para que se propague el RC
            if any(rc != 0 for rc in res_emp.values()):
                raise RuntimeError(f"Conversion incompleta para {emp}: {res_emp}")
            return 0

        # Tambien se pueden correr las dos empresas en paralelo
        safe_log(lambda: Logger.write_log().log_all('info', f'Empresas a convertir: {empresas_a_convertir}', logger_console, logger))
        outer_tasks = [(f"EMP_{emp}", (lambda emp=emp: _convertir_por_empresa(emp))) for emp in empresas_a_convertir]
        res_all = _run_parallel(outer_tasks, logger, logger_console, titulo="Validar_HSH (todas las empresas)")

    elif modo == 'jobs':
        # Solo SCADA; no requiere paralelismo
        convertir_scada(empresa, logger, logger_console)

    elif modo == 'unifilares':
        res = _run_parallel(
            [
                ("SCADA",      lambda: convertir_scada(empresa, logger, logger_console)),
                ("UNIFILARES", lambda: convertir_unifilares(empresa, logger, logger_console)),
            ],
            logger, logger_console, titulo=f"Convertir_all[{empresa}]/unifilares"
        )
        if res.get("UNIFILARES", 1) == 0:
            safe_log(lambda: Logger.write_log().log_all('info', 'Convirtiendo ODSTXT -> CSV', logger_console, logger))
            conver_unifilares_to_csv(empresa, logger, logger_console)
        else:
            safe_log(lambda: Logger.write_log().log_all('error', 'Unifilares fallo, omitir ODSTXT -> CSV', logger_console, logger))

    Logger.write_log().log_all('info', 'Flujo conversion listo', logger_console, logger)


if __name__ == "__main__":
    main()
