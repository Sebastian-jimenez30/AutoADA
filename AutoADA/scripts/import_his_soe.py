# scripts/import_his_soe.py
# -*- coding: utf-8 -*-
"""
Consulta eventos SOE en HIS vÃ­a ODBC (PostgreSQL) y exporta CSV consolidado.

CAMBIO: SIEMPRE consolida TODO en data.csv
- Sin archivos por estaciÃ³n.
- --split-by-station solo controla si se consulta 1x1 por estaciÃ³n, pero
  todo va a data.csv.
- --as-data se mantiene por compatibilidad, pero se ignora: siempre escribe en data.csv.
- --append controla si se anexa o se sobreescribe data.csv.

Tabla:
- Deriva como public.soe_{mes}_{aÃ±o} (mes sin cero a la izquierda)
Rango:
- fecha Ãºnica + hora_inicio/hora_fin (HH:MM:SS.mmm)
Filtro:
- station_name LIKE :station (o split por estaciÃ³n si --split-by-station)
Orden:
- time ASC, milli_secs ASC, repeated_hour ASC, record ASC
Salida:
- Consolidado: out/pruebas/data.csv (o --outdir/data.csv)
"""

import os
import sys
import csv
import argparse
from datetime import datetime
from typing import List, Optional

# --- Utils del proyecto (tolerantes) ---
try:
    from utils.paths import output_root
except Exception:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from utils.paths import output_root  # type: ignore

# Logger tolerante
try:
    from scripts import _Logger as Logger
except Exception:
    try:
        import _Logger as Logger  # type: ignore
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger  # type: ignore

# pyodbc obligatorio
try:
    import pyodbc  # type: ignore
except Exception as e:
    print("Error: pyodbc no estÃ¡ instalado. InstÃ¡lalo con 'pip install pyodbc'.")
    raise

# ----------------------------
# Argumentos CLI
# ----------------------------
def _args():
    p = argparse.ArgumentParser(description="Importar SOE desde HIS (ODBC) y exportar CSV consolidado (data.csv).")

    p.add_argument("empresa", type=str, help="Empresa (ITCO, TRA, REPS, REPP...)")
    p.add_argument("--host", type=str, default=None, help="Hostname HIS (si no se pasa, usa HIS_HOSTS del entorno)")

    # Puede omitirse; acepta comodines
    p.add_argument("--station", type=str, default="%", help="Station Name (ej. SABA500 o patrÃ³n con %). Por defecto: '%' (todas).")

    p.add_argument("--fecha", type=str, required=True, help="Fecha YYYY-MM-DD (dÃ­a Ãºnico)")
    p.add_argument("--hora_inicio", type=str, required=True, help="Hora inicio HH:MM:SS.mmm")
    p.add_argument("--hora_fin", type=str, required=True, help="Hora fin HH:MM:SS.mmm")
    p.add_argument("--outdir", type=str, default=None, help="Carpeta de salida (por defecto: out/pruebas)")

    # Compat/banderas
    p.add_argument("--split-by-station", action="store_true",
                   help="Detecta station_name distintos y ejecuta una consulta por cada uno (TODO se consolida en data.csv).")
    p.add_argument("--as-data", action="store_true",
                   help="[Ignorado] Se mantiene por compatibilidad; siempre se escribe en data.csv.")
    p.add_argument("--append", action="store_true",
                   help="Anexa en data.csv sin repetir encabezado (si no se usa, sobreescribe).")
    p.add_argument("--overwrite", action="store_true",
                   help="Sobrescribe data.csv (por defecto, si existe se apende sin header).")

    return p.parse_args()

# ----------------------------
# Helpers
# ----------------------------
def _parse_ts(fecha: str, hora: str) -> datetime:
    return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S.%f")

def _table_name(fecha: str) -> str:
    dt = datetime.strptime(fecha, "%Y-%m-%d")
    mes = dt.month  # sin cero a la izquierda
    anio = dt.year
    return f"public.soe_{mes}_{anio}"

def _conn_str(host: str) -> str:
    driver = os.environ.get("ODBC_DRIVER", "").strip()
    db     = os.environ.get("ODBC_DB", "").strip()
    user   = os.environ.get("ODBC_USER", "").strip()
    pwd    = os.environ.get("ODBC_PASS", "").strip()
    port   = os.environ.get("ODBC_PORT", "5432").strip()

    if not all([driver, db, user, pwd]):
        raise RuntimeError("Faltan variables ODBC en entorno: ODBC_DRIVER / ODBC_DB / ODBC_USER / ODBC_PASS")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host};"
        f"PORT={port};"
        f"DATABASE={db};"
        f"UID={user};"
        f"PWD={pwd};"
        f"SSLmode=require"
    )

def _try_connect(hosts: List[str]) -> pyodbc.Connection:
    last_err: Optional[Exception] = None
    for h in hosts:
        h = h.strip()
        if not h:
            continue
        try:
            conn = pyodbc.connect(_conn_str(h), autocommit=False, timeout=15)
            return conn
        except Exception as e:
            last_err = e
    raise RuntimeError(f"No fue posible conectarse a ninguno de los hosts HIS: {hosts}. Ãšltimo error: {last_err}")

def _out_base(outdir: Optional[str]) -> str:
    base = outdir or os.path.join(output_root(), "out", "pruebas")
    os.makedirs(base, exist_ok=True)
    return base

def _data_path(outdir: Optional[str]) -> str:
    return os.path.join(_out_base(outdir), "data.csv")

_HEADERS = ["time", "milli_secs", "station_name", "point_name", "state_text", "osi_key", "timequality", "scanquality", "site_id"]


def _select_sql(table: str, station_clause: str) -> str:
    return f"""
        SELECT
            "time",
            milli_secs,
            station_name,
            point_name,
            state_text,
            osi_key,
            timequality,
            scanquality,
            site_id
        FROM {table}
        WHERE {station_clause}
          AND "time" >= ?
          AND "time" <= ?
        ORDER BY "time" ASC, milli_secs ASC, repeated_hour ASC, record ASC
    """


def _parse_station_filters(raw: Optional[str]) -> List[str]:
    """Normaliza la entrada `--station` para soportar mÃºltiples estaciones en una sola consulta."""
    if raw is None:
        return ["%"]

    text = raw.strip()
    if not text:
        return ["%"]

    lowered = text.lower()
    if lowered in {"estacion...", "estaciÃ³n..."}:
        return ["%"]

    # Permite separadores coma, punto y coma o barra vertical.
    separators = [",", ";", "|"]
    for sep in separators:
        text = text.replace(sep, ",")

    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return ["%"]

    if any(part == "%" for part in parts):
        return ["%"]

    seen = set()
    normalized: List[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            normalized.append(part)

    return normalized or ["%"]


def _station_clause(patterns: List[str]) -> tuple[str, List[str]]:
    """Construye clÃ¡usula SQL para filtrar por estaciones usando LIKE."""
    if not patterns:
        return "station_name LIKE ?", ["%"]

    if any(p == "%" for p in patterns):
        return "station_name LIKE ?", ["%"]

    if len(patterns) == 1:
        return "station_name LIKE ?", patterns

    clause = " OR ".join("station_name LIKE ?" for _ in patterns)
    return f"({clause})", patterns

def _dump_query_to_csv(cur: pyodbc.Cursor, sql: str, params: tuple, out_csv: str, write_header: bool) -> int:
    """
    Ejecuta 'sql' con 'params' y vuelca a 'out_csv'. Devuelve filas escritas (sin contar header).
    """
    total_rows = 0
    cur.execute(sql, params)
    mode = "a" if os.path.exists(out_csv) and not write_header else "w"
    with open(out_csv, mode, encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(_HEADERS)
        while True:
            rows = cur.fetchmany(5000)
            if not rows:
                break
            for r in rows:
                t = r[0]
                t_str = t.strftime("%Y-%m-%d %H:%M:%S") if hasattr(t, "strftime") else str(t)
                writer.writerow([
                    t_str,
                    r[1],  # milli_secs
                    r[2],  # station_name
                    r[3],  # point_name
                    r[4],  # state_text
                    r[5],  # osi_key
                    r[6],  # timequality
                    r[7],  # scanquality
                    r[8],  # site_id
                ])
                total_rows += 1
    return total_rows

# ----------------------------
# Main
# ----------------------------
def main():
    args = _args()

    empresa = args.empresa.strip().upper()
    station_filters = _parse_station_filters(args.station)
    station_label = ", ".join(station_filters)

    fecha = args.fecha.strip()
    hini  = args.hora_inicio.strip()
    hfin  = args.hora_fin.strip()

    # Logger
    log_dir = os.path.join(output_root(), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "pruebas.log")
    logger, logger_console = Logger.initlog(log_path)
    Logger.write_log().log_all(
        "info",
        f"Exportacion HIS {empresa} estacion={station_label} {fecha} {hini}-{hfin}",
        logger_console, logger
    )

    # Validaciones bÃ¡sicas
    try:
        t0 = _parse_ts(fecha, hini)
        t1 = _parse_ts(fecha, hfin)
    except Exception as e:
        Logger.write_log().log_all("error", f"Formato de tiempo invalido: {e}", logger_console, logger)
        sys.exit(2)
    if t0 > t1:
        Logger.write_log().log_all("error", "Hora inicio mayor que hora fin", logger_console, logger)
        sys.exit(2)

    table = _table_name(fecha)
    station_clause, station_params = _station_clause(station_filters)
    sql = _select_sql(table, station_clause)
    data_csv = _data_path(args.outdir)
    sql_params = tuple(station_params + [t0, t1])

    # Hosts: CLI --host o entorno HIS_HOSTS (coma-separados)
    if args.host:
        hosts = [args.host]
    else:
        env_hosts = os.environ.get("HIS_HOSTS", "")
        hosts = [h for h in env_hosts.split(",") if h.strip()]
    if not hosts:
        Logger.write_log().log_all("error", "Host ausente (usa --host o HIS_HOSTS)", logger_console, logger)
        sys.exit(2)

    # ConexiÃ³n
    try:
        conn = _try_connect(hosts)
        Logger.write_log().log_all("info", f"Conectado a HIS {conn.getinfo(pyodbc.SQL_SERVER_NAME)}", logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all("error", f"Fallo conexion HIS: {e}", logger_console, logger)
        sys.exit(3)

    try:
        with conn.cursor() as cur:
            # PreparaciÃ³n de archivo de salida:
            # - Si --overwrite: limpiar y escribir header en la primera tanda.
            # - Si no: si existe -> append sin header; si no existe -> crear con header.
            if getattr(args, "overwrite", False):
                try:
                    if os.path.exists(data_csv):
                        os.remove(data_csv)
                except Exception:
                    pass
                write_header_next = True
            else:
                write_header_next = not os.path.exists(data_csv)

            if args.split_by_station:
                Logger.write_log().log_all(
                    "warn",
                    "--split-by-station ignorada (consulta unica)",
                    logger_console,
                    logger,
                )

            rows = _dump_query_to_csv(cur, sql, sql_params, data_csv, write_header=write_header_next)
            write_header_next = False
            Logger.write_log().log_all(
                "info",
                f"Exportacion lista (1 consulta): {rows} filas -> {data_csv}",
                logger_console,
                logger,
            )

            # Imprimir SIEMPRE la ruta consolidada para que la UI la capture
            print(data_csv)

        conn.commit()
        sys.exit(0)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        Logger.write_log().log_all("error", f"Consulta fallo: {e}", logger_console, logger)
        sys.exit(4)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
