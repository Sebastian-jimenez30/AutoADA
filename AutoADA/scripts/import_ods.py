# -*- coding: utf-8 -*-
"""
SOE Local (v2, compat itcosas pipeline) — Comportamiento alineado con SOE_LOCAL.py
- Detecta encoding (utf-16, latin-1, utf-8) y delimitador (',', ';', '\t', '|').
- Normaliza encabezado 'Timestamp (hora estándar de Colombia)' -> 'Timestamp'.
- Mapear columnas requeridas (Timestamp, Tag Name, Category, Message) con variantes.
- Parseo de Tag Name por '|' -> Tension / Bahia / Nomenclatura / Equipo.
- IOA desde Tag Name (3-4 dígitos) o, si no, desde Category.
- Mapea Event textual -> event numérico con Dicc_Events (Inactiva/Activa/Inactivo/Activo).
- Arma 'time' = 'YYYY-MM-DD HH:MM:SS.mmm' y guarda out/pruebas/SOE_Local.csv.
- Imprime la ruta resultante para que la UI la capture.
"""

import os
import re
import sys
import glob
import argparse
from typing import Optional, Dict, List

# pandas obligatorio
try:
    import pandas as pd  # type: ignore
except Exception as e:
    print("error: No se pudo importar pandas. Instálalo con 'pip install pandas'.")
    raise

# Rutas (tolerante exe/dev)
try:
    from utils.paths import output_root
except Exception:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    try:
        from utils.paths import output_root  # type: ignore
    except Exception:
        def output_root(app_name: str = "ADA-DOT") -> str:
            root = os.getcwd()
            for d in ("out", "log"):
                os.makedirs(os.path.join(root, d), exist_ok=True)
            return root

# Logger tolerante
try:
    from scripts import _Logger as Logger  # type: ignore
except Exception:
    try:
        import _Logger as Logger  # type: ignore
    except Exception:
        class _DummyLogger:
            @staticmethod
            def initlog(path):
                return None, None
            @staticmethod
            def write_log():
                class _W:
                    def log_all(self, level, msg, *a, **kw):
                        print(f"{level.upper()}: {msg}")
                return _W()
        Logger = _DummyLogger()  # type: ignore

# --- utilidades de importación remota (SCADA/HSH) reutilizadas ---
try:
    from scripts.import_base import (
        load_profiles_config,
        resolve_usecase,
        make_target_dir,
        reset_dir,
        sftp_transfer,
        log_all,
        log_files,
        replace_server_prefix,
        related_company,
        related_server_candidates,
    )
except Exception:
    try:
        from import_base import (
            load_profiles_config,
            resolve_usecase,
            make_target_dir,
            reset_dir,
            sftp_transfer,
            log_all,
            log_files,
            replace_server_prefix,
            related_company,
            related_server_candidates,
        )
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        from import_base import (
            load_profiles_config,
            resolve_usecase,
            make_target_dir,
            reset_dir,
            sftp_transfer,
            log_all,
            log_files,
            replace_server_prefix,
            related_company,
            related_server_candidates,
        )

try:
    from scripts.functions import sshserver
except Exception:
    try:
        from functions import sshserver
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        from functions import sshserver  # type: ignore

try:
    from scripts.import_resolvers import display_by_domain
except Exception:
    try:
        from import_resolvers import display_by_domain
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        from import_resolvers import display_by_domain  # type: ignore


def run(server: str,
        empresa: str,
        usecase: Optional[str],
        flex: bool,
        logger,
        logger_console):
    """
    Importa archivos ODS desde el servidor remoto (SFTP) siguiendo la configuración del perfil.
    """
    cfg = load_profiles_config()
    resolved = resolve_usecase(cfg, usecase)
    ods_cfg = resolved.get("ods") or {}

    if not ods_cfg.get("enabled", False):
        log_all('info', f"ODS deshabilitado para usecase={usecase}", logger_console, logger)
        return

    target_dir = make_target_dir(empresa, "ODS")
    reset_dir(target_dir, logger_console, logger)

    client = sshserver(server, logger, logger_console)
    try:
        from_path = ods_cfg.get("from_path")
        if not from_path:
            resolver = ods_cfg.get("from_path_resolver")
            if resolver == "display_by_domain":
                from_path = display_by_domain(client, logger_console, logger)
            elif resolver:
                raise RuntimeError(f"Resolver ODS desconocido: {resolver}")
            else:
                raise RuntimeError("ODS requiere 'from_path' o 'from_path_resolver'.")

        pattern = ods_cfg.get("pattern") or ".ODS"

        transferred, total, names = sftp_transfer(
            client,
            from_path,
            target_dir,
            files=None,
            pattern=pattern,
            logger_console=logger_console,
            logger=logger,
        )

        if transferred == total:
            log_all('info', f"ODS transferencia OK {transferred} archivos", logger_console, logger)
        else:
            log_all('warning', f"ODS transferencia incompleta {transferred}/{total} archivos", logger_console, logger)

        if flex:
            rel = related_company(empresa)
            if rel:
                candidates = related_server_candidates(server, empresa) or [replace_server_prefix(server, empresa)]
                last_error: Optional[Exception] = None
                for server_rel in candidates:
                    try:
                        log_all('info', f"Importacion ODS flex {rel} via {server_rel}", logger_console, logger)
                        run(server_rel, rel, usecase, False, logger, logger_console)
                        break
                    except Exception as exc:
                        last_error = exc
                        log_all('error', f"ODS flex fallo con {server_rel}: {exc}", logger_console, logger)
                        continue
                else:
                    if last_error:
                        raise last_error
    finally:
        try:
            client.close()
            log_files('debug', f'Connection with server {server} is close', logger)
        except Exception:
            pass


# -----------------------------
# Config / CLI
# -----------------------------
Dicc_Events: Dict[str, int] = {
    "Inactiva": 0,
    "Activa": 1,
    "Inactivo": 0,  # variantes
    "Activo": 1,
}

def _args():
    p = argparse.ArgumentParser(description="SOE Local (v2 compat) — Procesa CSV base de SOE de la SE al estilo SOE_LOCAL.py")
    p.add_argument("--input", type=str, default=None,
                   help="Ruta al CSV base. Si no se pasa, se buscará por patrón en el cwd (out/pruebas).")
    p.add_argument("--pattern", type=str, default="EventosDiario",
                   help="Patrón a buscar en nombres de archivos (por defecto: 'EventosDiario').")
    p.add_argument("--outdir", type=str, default=None,
                   help="Directorio de salida (por defecto: out/pruebas).")
    return p.parse_args()


# -----------------------------
# Utilidades
# -----------------------------
def _search_base_dir(outdir: Optional[str]) -> str:
    # En el flujo, trabajamos en out/pruebas
    if outdir:
        return os.path.abspath(outdir)
    return os.path.join(output_root(), "out", "pruebas")

def _find_input_file(base_dir: str, pattern: str) -> str:
    # Coincidencias por startswith primero
    cands = [os.path.join(base_dir, f)
             for f in os.listdir(base_dir)
             if f.lower().endswith(".csv") and f.startswith(pattern)]
    if not cands:
        # fallback: contiene el patrón
        cands = glob.glob(os.path.join(base_dir, f"*{pattern}*.csv"))
    if not cands:
        raise FileNotFoundError(f"No se encontró ningún CSV que coincida con '{pattern}' en {base_dir}.")
    if len(cands) > 1:
        # Elige el más reciente
        cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        print(f"warn: múltiples archivos con '{pattern}'. Se usará el más reciente: {os.path.basename(cands[0])}")
    return cands[0]

def _normalize_header_timestamp_inplace(path: str, encodings: List[str]) -> None:
    """
    Normaliza 'Timestamp (hora estándar de Colombia)' -> 'Timestamp' in-place.
    Mantiene el encoding original con el que se pudo leer.
    """
    last_err = None
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            content2 = content.replace('"Timestamp (hora estándar de Colombia)"', '"Timestamp"')
            content2 = content2.replace('Timestamp (hora estándar de Colombia)', 'Timestamp')
            content2 = content2.replace('Timestamp (hora estÃ¡ndar de Colombia)', 'Timestamp')
            if content2 != content:
                with open(path, "w", encoding=enc) as f:
                    f.write(content2)
                print("info: Encabezado de Timestamp normalizado.")
            return
        except Exception as e:
            last_err = e
            continue
    if last_err:
        print(f"warn: No se pudo asegurar normalización de encabezado: {last_err}")

def _detect_encoding(path: str) -> Optional[str]:
    for enc in ("utf-16", "latin-1", "utf-8"):
        try:
            with open(path, "r", encoding=enc) as f:
                f.readline()
            print(f"info: Encoding detectado: {enc}")
            return enc
        except Exception:
            continue
    return None

def _detect_delimiter(path: str, encoding: str) -> str:
    with open(path, "r", encoding=encoding, errors="replace") as f:
        first = f.readline()
    candidates = [",", ";", "\t", "|"]
    counts = {d: first.count(d) for d in candidates}
    delim = max(counts, key=counts.get)
    print(f"info: Delimitador detectado: '{delim}' (conteo {counts[delim]})")
    return delim

# columnas requeridas y sus alias
COLS_REQUERIDAS = {
    "Timestamp": ["Timestamp", "timestamp", "Time", "time", "DateTime", "datetime"],
    "Tag Name": ["Tag Name", "TagName", "tag_name", "Tag", "tag", "Name", "name"],
    "Category": ["Category", "category", "Cat", "cat", "Type", "type"],
    "Message":  ["Message", "message", "Msg", "msg", "Description", "description", "Event", "event"],
}

def _find_col(df_cols: List[str], posibles: List[str]) -> Optional[str]:
    for name in posibles:
        if name in df_cols:
            return name
    return None

def _is_valid_date_ddmmyyyy(s: str) -> bool:
    return bool(re.match(r"^\d{2}/\d{2}/\d{4}$", s))

# -----------------------------
# Main
# -----------------------------
def main():
    args = _args()

    # Logger
    log_dir = os.path.join(output_root(), "log")
    os.makedirs(log_dir, exist_ok=True)
    logger, logger_console = Logger.initlog(os.path.join(log_dir, "pruebas.log"))
    wl = Logger.write_log()

    try:
        outdir = args.outdir or os.path.join(output_root(), "out", "pruebas")
        os.makedirs(outdir, exist_ok=True)

        # Localizar archivo base
        if args.input:
            in_path = os.path.abspath(args.input)
            if not os.path.isfile(in_path):
                raise FileNotFoundError(f"No existe el archivo indicado: {in_path}")
        else:
            base_dir = _search_base_dir(args.outdir)
            in_path = _find_input_file(base_dir, args.pattern)

        wl.log_all("info", f"[SOE_LOCAL_V2_COMPAT] Archivo base: {in_path}", logger_console, logger)
        print(f"info: Archivo encontrado: {os.path.basename(in_path)}")

        # Normalizar encabezado Timestamp (in-place, mejor esfuerzo)
        _normalize_header_timestamp_inplace(in_path, ["utf-16", "latin-1", "utf-8"])

        # Detectar encoding y delimitador
        enc = _detect_encoding(in_path)
        if not enc:
            raise RuntimeError("No se pudo detectar el encoding del archivo.")
        delim = _detect_delimiter(in_path, enc)

        # Leer CSV crudo
        df_raw = pd.read_csv(in_path, encoding=enc, delimiter=delim)
        print(f"info: CSV leído. Shape={df_raw.shape}")
        print(f"info: Columnas originales: {list(df_raw.columns)}")

        # Mapear columnas requeridas
        mapeo: Dict[str, str] = {}
        faltantes: List[str] = []
        for canon, aliases in COLS_REQUERIDAS.items():
            col = _find_col(list(df_raw.columns), aliases)
            if col:
                mapeo[col] = canon
            else:
                faltantes.append(canon)
        if faltantes:
            raise KeyError(f"Faltan columnas requeridas: {faltantes}. Disponibles: {list(df_raw.columns)}")

        # Quedarnos con las necesarias y renombrar a canónicas
        df = df_raw[list(mapeo.keys())].rename(columns=mapeo).copy()
        # Limpiezas básicas
        for c in df.columns:
            if df[c].dtype == "object":
                df[c] = df[c].astype(str).str.strip()

        # Procesamiento fila a fila (alineado a SOE_LOCAL.py)
        columnas = [
            "Fecha", "Hora", "Subestacion", "Tension", "Equipo", "Bahia", "FP",
            "Nomenclatura", "IOA", "Signal", "Event", "col10", "col11", "col12", "col13"
        ]
        filas = []
        lineas_proc = lineas_ioa = lineas_fecha_ok = 0

        for _, row in df.iterrows():
            lineas_proc += 1
            timestamp = str(row.get("Timestamp", ""))
            tag_name  = str(row.get("Tag Name", ""))
            category  = str(row.get("Category", ""))
            message   = str(row.get("Message", ""))

            # Parse timestamp "YYYY-MM-DD HH:MM:SS.mmm"
            try:
                if "." in timestamp:
                    dt_part, ms = timestamp.split(".", 1)
                else:
                    dt_part, ms = timestamp, "000"
                if " " in dt_part:
                    fecha_iso, hora = dt_part.split(" ", 1)
                else:
                    continue  # formato inesperado
                fecha_ddmmyyyy = pd.to_datetime(fecha_iso, errors="coerce").strftime("%d/%m/%Y")
            except Exception:
                continue

            # IOA: primero en Tag Name (3–4 dígitos), luego en Category
            ioa = None
            parts_tag = [p.strip() for p in tag_name.split("|") if p.strip()]
            for p in parts_tag:
                if p.isdigit() and 100 <= int(p) <= 9999:  # rango laxo 3–4 dígitos
                    ioa = p
                    break
            if not ioa:
                nums = re.findall(r"\b\d{3,4}\b", category)
                for n in nums:
                    ioa = n
                    break
            if not ioa:
                continue

            lineas_ioa += 1

            # Tension, Bahia, Nomenclatura (intermedios), Equipo (último)
            tension = parts_tag[0] if len(parts_tag) > 0 else ""
            bahia   = parts_tag[1] if len(parts_tag) > 1 else ""
            cod_int = parts_tag[2:-1] if len(parts_tag) > 3 else []
            nomen   = " - ".join(cod_int) if cod_int else ""
            equipo  = parts_tag[-1] if len(parts_tag) > 0 else ""

            row_out = [
                fecha_ddmmyyyy,  # Fecha
                hora,            # Hora
                "",              # Subestacion (no provista)
                tension,         # Tension
                equipo,          # Equipo
                bahia,           # Bahia
                "",              # FP
                nomen,           # Nomenclatura
                ioa,             # IOA
                tag_name,        # Signal
                message,         # Event (texto)
                "", "", "",      # col10-12
                ms[:3].zfill(3)  # col13 -> milli_secs
            ]

            if _is_valid_date_ddmmyyyy(fecha_ddmmyyyy):
                lineas_fecha_ok += 1
                filas.append(dict(zip(columnas, row_out)))

            if lineas_proc % 50 == 0:
                print(f"info: Progreso {lineas_proc} filas, {lineas_ioa} con IOA, {len(filas)} válidas")

        print("\n=== RESUMEN ===")
        print(f"Líneas procesadas: {lineas_proc}")
        print(f"Líneas con IOA: {lineas_ioa}")
        print(f"Líneas con fecha válida: {lineas_fecha_ok}")
        print(f"Filas salida: {len(filas)}")

        if not filas:
            raise RuntimeError("No se generaron filas válidas para SOE_Local.")

        df_eventos = pd.DataFrame(filas)

        # Normaliza Event textual y crea 'event' numérico
        df_eventos["Event"] = df_eventos["Event"].astype(str).str.strip().str.capitalize()
        df_eventos["event"] = df_eventos["Event"].map(Dicc_Events).fillna(-1).astype(int)

        # Fecha a YYYY/MM/DD y milli_secs desde col13
        df_eventos["Fecha"] = pd.to_datetime(df_eventos["Fecha"], format="%d/%m/%Y").dt.strftime("%Y/%m/%d")
        df_eventos["milli_secs"] = df_eventos["col13"].astype(str)

        # Columnas finales estilo SOE_LOCAL.py
        cols_finales = [
            "Fecha", "Hora", "milli_secs", "Tension", "Bahia", "Equipo",
            "Nomenclatura", "Signal", "Event", "IOA", "event"
        ]
        df_eventos = df_eventos[cols_finales]

        # time = 'YYYY-MM-DD HH:MM:SS.mmm'
        dt = pd.to_datetime(df_eventos["Fecha"] + " " + df_eventos["Hora"], format="%Y/%m/%d %H:%M:%S", errors="coerce")
        df_eventos["time"] = dt.dt.strftime("%Y-%m-%d %H:%M:%S") + "." + df_eventos["milli_secs"].astype(str).str.zfill(3)

        # Guardar
        out_csv = os.path.join(outdir, "SOE_Local.csv")
        df_eventos.to_csv(out_csv, index=False, encoding="utf-8-sig")

        wl.log_all("info", f"[SOE_LOCAL_V2_COMPAT] Generado: {out_csv}", logger_console, logger)
        print(out_csv)  # <- la UI captura esta ruta
        print("info: SOE_Local.csv generado correctamente. ¡Fin!")

    except Exception as e:
        wl.log_all("error", f"[SOE_LOCAL_V2_COMPAT] Error: {e}", logger_console, logger)
        print(f"error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
