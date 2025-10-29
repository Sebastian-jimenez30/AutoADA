# -*- coding: utf-8 -*-
"""
SOE Local (v2) — Limpia y transforma el CSV base de SOE de la SE.

Entradas:
  - Por defecto, busca un archivo cuyo nombre contenga el patrón 'SOE_SE'
    en el directorio de trabajo actual (cwd). En nuestro pipeline, cwd=out/pruebas.
  - Opcionalmente, se puede pasar --input <ruta> o --pattern <texto>.

Transformaciones principales:
  - Filtra Category != 'Security' y != ''.
  - Convierte 'Timestamp' -> datetime y crea 'milli_secs'.
  - Renombra 'Timestamp' -> 'time'.
  - Extrae 'Tension' (ej. '115kV') desde 'Tag Name' y la quita del texto.
  - Parte 'Tag Name' en 'Bahia' y 'Name_SE' (por doble espacio).
  - Divide 'Category' en 'Name_Monarch' y 'IOA' (por coma ',').
  - Mapea 'Message' -> 'Event' usando Dicc_Events {Inactivo/Activo/Intermediate/Off/On/Bad}.

Salida:
  - out/pruebas/SOE_Local.csv  (o --outdir/SOE_Local.csv si se indicó)

Notas:
  - Codificación de lectura con fallback (utf-8 luego latin1).
  - Escritura en 'utf-8-sig' (amigable con Excel).
  - Mensajes de progreso/imprevistos compatibles con la consola de la app.
"""

import os
import re
import sys
import glob
import argparse
from typing import Optional

# --- Dependencias externas ---
try:
    import pandas as pd  # type: ignore
except Exception as e:
    print("error: No se pudo importar pandas. Instálalo con 'pip install pandas'.")
    raise

# --- Utils de rutas (tolerante para ejecución directa o empaquetada) ---
try:
    from utils.paths import output_root
except Exception:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    try:
        from utils.paths import output_root  # type: ignore
    except Exception as e:
        # Fallback mínimo si no existe el módulo (modo suelto)
        def output_root(app_name: str = "ADA-DOT") -> str:
            root = os.getcwd()
            for d in ("out", "log"):
                os.makedirs(os.path.join(root, d), exist_ok=True)
            return root

# --- Logger tolerante (alineado con otros scripts del proyecto) ---
try:
    from scripts import _Logger as Logger  # type: ignore
except Exception:
    try:
        import _Logger as Logger  # type: ignore
    except Exception:
        class _DummyLogger:
            @staticmethod
            def initlog(path):
                class _C: pass
                return None, None
            @staticmethod
            def write_log():
                class _W:
                    def log_all(self, level, msg, *a, **kw):
                        print(f"{level.upper()}: {msg}")
                return _W()
        Logger = _DummyLogger()  # type: ignore

# ---------------------------------
# Config / CLI
# ---------------------------------
Dicc_Events = {
    "Inactivo": 0,
    "Activo": 1,
    "Intermediate": 0,
    "Off": 1,
    "On": 2,
    "Bad": 3,
}

def _args():
    p = argparse.ArgumentParser(description="SOE Local (v2) — Procesa CSV base de SOE de la SE.")
    p.add_argument("--input", type=str, default=None,
                   help="Ruta al CSV base (si no se pasa, se buscará por patrón en el cwd).")
    p.add_argument("--pattern", type=str, default="SOE_SE",
                   help="Patrón a buscar en nombres de archivos del cwd (por defecto: 'SOE_SE').")
    p.add_argument("--outdir", type=str, default=None,
                   help="Directorio de salida (por defecto: out/pruebas).")
    return p.parse_args()

# ---------------------------------
# Utilidades
# ---------------------------------
def _move_column(df: "pd.DataFrame", col: str, pos: int) -> None:
    if col not in df.columns:
        return
    col_data = df.pop(col)
    df.insert(pos, col, col_data)

def _read_csv_with_fallback(path: str) -> "pd.DataFrame":
    last_err: Optional[Exception] = None
    for enc in ("utf-8", "utf-8-sig", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"No se pudo leer CSV '{path}' con codificaciones comunes. Último error: {last_err}")

def _find_input_file(cwd: str, pattern: str) -> str:
    # preferimos coincidencias que contengan pattern (case-insensitive)
    cand = []
    for f in os.listdir(cwd):
        if pattern.lower() in f.lower() and f.lower().endswith(".csv"):
            cand.append(os.path.join(cwd, f))
    if not cand:
        # fallback: cualquier CSV que contenga el patrón (glob permisivo)
        cand = glob.glob(os.path.join(cwd, f"*{pattern}*.csv"))
    if not cand:
        raise FileNotFoundError(f"No se encontró ningún CSV que contenga '{pattern}' en {cwd}.")
    if len(cand) == 1:
        return cand[0]
    # Si hay más de uno, tomamos el más reciente por mtime para comportamiento determinista
    cand.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    print(f"warn: múltiples archivos que coinciden con '{pattern}'. Se usará el más reciente: {os.path.basename(cand[0])}")
    return cand[0]

def _extract_tension(tag_name: str) -> Optional[str]:
    if not isinstance(tag_name, str):
        return None
    m = re.search(r"\d+kV", tag_name)
    return m.group(0) if m else None

def _remove_tension(tag_name: str) -> str:
    if not isinstance(tag_name, str):
        return ""
    return re.sub(r"\d+kV\s+", "", tag_name)

def _split_tag_name(tag_name: str):
    if not isinstance(tag_name, str):
        return "", ""
    if "  " in tag_name:
        parts = tag_name.split("  ", 1)
    else:
        parts = ["", tag_name]
    # siempre devolvemos 2
    if len(parts) == 1:
        parts = ["", parts[0]]
    return parts[0], parts[1]

def _ensure_cols(df: "pd.DataFrame", required: list[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas en el CSV de entrada: {', '.join(missing)}")

# ---------------------------------
# Main
# ---------------------------------
def main():
    args = _args()

    # Logger
    log_dir = os.path.join(output_root(), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "pruebas.log")
    logger, logger_console = Logger.initlog(log_path)
    wl = Logger.write_log()

    try:
        cwd = os.getcwd()
        outdir = args.outdir or os.path.join(output_root(), "out", "pruebas")
        os.makedirs(outdir, exist_ok=True)

        search_base = outdir if args.outdir else cwd

        # Localizar archivo base
        if args.input:
            in_path = os.path.abspath(args.input)
            if not os.path.isfile(in_path):
                raise FileNotFoundError(f"No existe el archivo indicado: {in_path}")
        else:
            in_path = _find_input_file(search_base, args.pattern)

        wl.log_all("info", f"[SOE_LOCAL_V2] Archivo base: {in_path}", logger_console, logger)
        print(f"info: Archivo encontrado: {os.path.basename(in_path)}")

        # Leer CSV (con fallback de encoding)
        df = _read_csv_with_fallback(in_path)

        # Validar columnas mínimas
        _ensure_cols(df, ["Category", "Timestamp", "Tag Name", "Message"])

        # Filtrado Category
        mask = (df["Category"].astype(str) != "Security") & (df["Category"].astype(str) != "")
        df = df[mask].copy()

        # Timestamps
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        before = len(df)
        df = df.dropna(subset=["Timestamp"]).copy()
        if len(df) != before:
            print(f"warn: {before - len(df)} filas descartadas por Timestamp inválido.")

        # milli_secs + rename time
        df["milli_secs"] = (df["Timestamp"].dt.microsecond // 1000).astype("Int64")
        df = df.rename(columns={"Timestamp": "time"})

        # Tension (de 'Tag Name'), quitar del texto, partir en Bahía / Nombre
        df["Tension"] = df["Tag Name"].apply(_extract_tension)
        df["Tag Name"] = df["Tag Name"].apply(_remove_tension)
        df["Bahia"], df["Name_SE"] = zip(*df["Tag Name"].apply(_split_tag_name))

        # Orden sugerido de columnas nuevas
        _move_column(df, "milli_secs", 1)
        _move_column(df, "Tension", 2)
        _move_column(df, "Bahia", 3)
        _move_column(df, "Name_SE", 4)

        # Category -> Name_Monarch, IOA (separado por coma)
        # Si no hay coma, IOA queda vacío
        name_monarch = []
        ioa_vals = []
        for v in df["Category"].astype(str).fillna(""):
            if "," in v:
                a, b = v.split(",", 1)
            else:
                a, b = v, ""
            name_monarch.append(a.strip().lstrip())
            ioa_vals.append(b.strip())
        df["Name_Monarch"] = name_monarch
        df["IOA"] = ioa_vals
        _move_column(df, "Name_Monarch", 5)
        _move_column(df, "IOA", 6)

        # Drop columnas de trabajo
        df = df.drop(columns=["Tag Name", "Category"], errors="ignore")

        # Message -> Event (map con limpieza)
        df["Message"] = df["Message"].astype(str).str.strip()
        df["Event"] = df["Message"].map(Dicc_Events)
        before = len(df)
        df = df.dropna(subset=["Event"]).copy()
        df["Event"] = df["Event"].astype(int)
        if len(df) != before:
            print(f"warn: {before - len(df)} filas descartadas por Message no mapeable.")

        # Guardar salida
        out_csv = os.path.join(outdir, "SOE_Local.csv")
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")

        wl.log_all("info", f"[SOE_LOCAL_V2] Generado: {out_csv}", logger_console, logger)
        print(out_csv)  # <- la app puede capturar esta ruta
        print("info: SOE_Local.csv generado correctamente. ¡Fin!")

    except Exception as e:
        wl.log_all("error", f"[SOE_LOCAL_V2] Error: {e}", logger_console, logger)
        print(f"error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
