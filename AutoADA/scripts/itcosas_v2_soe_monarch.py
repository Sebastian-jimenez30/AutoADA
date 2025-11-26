# -*- coding: utf-8 -*-
"""
SOE Monarch (v2) — Enlaza HIS con SCADA (IOA y event) con joins robustos.

Mejoras clave:
- Normaliza pRTU (float/str) -> 'zzz' con zfill(3); si --prtu=auto y no se detecta, NO filtra.
- Une HIS.osi_key con SCADA 32_10.Key SIN ceros a la izquierda (Key.lstrip('0')).
- Hace lo mismo para 10_4.Key (pStates) para mapear event desde 19_1.names_*.
- Construye time 'YYYY-MM-DD HH:MM:SS.mmm' y guarda out/pruebas/SOE_Monarch.csv.
"""

import os
import sys
import glob
import argparse
from typing import Optional, List

import warnings
warnings.filterwarnings("ignore")

# --- pandas obligatorio ---
try:
    import pandas as pd  # type: ignore
except Exception:
    print("error: No se pudo importar pandas. Instálalo con 'pip install pandas'.")
    raise

# --- Rutas del proyecto (tolerante para dev/pyinstaller) ---
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

# --- Logger tolerante, alineado con otros scripts ---
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

# Detectores pRTU (opcionales, si existen en tu repo v1)
try:
    from scripts.pyp_soe_monarch import (  # type: ignore
        _extraer_prtu_desde_checklist as detect_prtu_from_checklist,
        _prtu_from_station as detect_prtu_from_station,
    )
except Exception:
    try:
        from pyp_soe_monarch import (  # type: ignore
            _extraer_prtu_desde_checklist as detect_prtu_from_checklist,  # type: ignore
            _prtu_from_station as detect_prtu_from_station,  # type: ignore
        )
    except Exception:
        detect_prtu_from_checklist = None  # type: ignore
        detect_prtu_from_station = None  # type: ignore


# ---------------------------------
# CLI
# ---------------------------------
def _args():
    p = argparse.ArgumentParser(description="SOE Monarch (v2) — Enlaza HIS con SCADA (IOA y event).")
    p.add_argument("empresa", type=str, help="Empresa (para ubicar out/<empresa>/SCADA por defecto).")
    # alias
    p.add_argument("--his-data", "--his", dest="his_data", type=str, default=None,
                   help="Ruta al CSV consolidado de HIS (data.csv o data-*.csv).")
    p.add_argument("--scada-dir", "--scada", dest="scada_dir", type=str, default=None,
                   help="Carpeta SCADA con 32_10.csv, 10_4.csv, 19_1.csv.")
    p.add_argument("--checklist", type=str, default=None,
                   help="Checklist STATUS/ANALOG para inferir pRTU automáticamente (opcional si usas --prtu).")
    p.add_argument("--station", type=str, default=None,
                   help="Nombre o identificador de estación (fallback para calcular pRTU).")
    p.add_argument("--prtu", type=str, default="auto",
                   help="Filtro pRTU para 32_10.csv; usa 'auto' para detectar; si no se detecta, NO filtra.")
    p.add_argument("--outdir", type=str, default=None, help="Carpeta de salida (default: out/pruebas).")
    return p.parse_args()

# ---------------------------------
# Utilidades
# ---------------------------------
def _read_csv(path: str, **kwargs) -> "pd.DataFrame":
    last = None
    for enc in ("utf-8", "utf-8-sig", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception as e:
            last = e
    raise RuntimeError(f"No se pudo leer '{path}' con codificaciones comunes. Último error: {last}")

def _scada_dir_for(empresa: str) -> str:
    return os.path.join(output_root(), "out", empresa, "SCADA")

def _find_his_data(cwd: str) -> str:
    direct = os.path.join(cwd, "data.csv")
    if os.path.isfile(direct):
        return direct
    cands = glob.glob(os.path.join(cwd, "data-*.csv"))
    if not cands:
        raise FileNotFoundError(f"No se encontró data.csv ni data-*.csv en {cwd}.")
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    if len(cands) > 1:
        print(f"warn: múltiples data-*.csv. Se usará el más reciente: {os.path.basename(cands[0])}")
    return cands[0]

def _require_files(dirpath: str, files: List[str]) -> List[str]:
    missing = []
    for f in files:
        if not os.path.isfile(os.path.join(dirpath, f)):
            missing.append(f)
    return missing

def _build_states_dict(df_states: "pd.DataFrame") -> dict:
    name_cols = [c for c in df_states.columns if c.startswith("names_")]
    name_cols.sort(key=lambda x: int(x.split("_")[1]) if "_" in x and x.split("_")[1].isdigit() else 999)

    dic = {}
    for _, row in df_states.iterrows():
        record = row.get("#record")
        record_values = {}
        for c in name_cols:
            v = row.get(c)
            if pd.notna(v):
                try:
                    idx = int(c.split("_")[1])
                except Exception:
                    continue
                record_values[str(v)] = idx
        if record_values:
            dic[record] = {
                "description": row.get("description"),
                "values": record_values
            }
    return dic


# ---------------------------------
# Main
# ---------------------------------
def main():
    args = _args()

    empresa = args.empresa.strip()
    outdir = args.outdir or os.path.join(output_root(), "out", "pruebas")
    os.makedirs(outdir, exist_ok=True)

    # Logger
    log_dir = os.path.join(output_root(), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "pruebas.log")
    logger, logger_console = Logger.initlog(log_path)
    wl = Logger.write_log()

    try:
        cwd = os.getcwd()

        # HIS data
        if args.his_data:
            his_path = os.path.abspath(args.his_data)
            if not os.path.isfile(his_path):
                raise FileNotFoundError(f"--his-data no existe: {his_path}")
        else:
            his_path = _find_his_data(cwd)
        wl.log_all("info", f"[SOE_MONARCH_V2] HIS data: {his_path}", logger_console, logger)
        print(f"info: HIS -> {os.path.basename(his_path)}")

        # SCADA dir
        scada_dir = args.scada_dir or _scada_dir_for(empresa)
        missing = _require_files(scada_dir, ["32_10.csv", "10_4.csv", "19_1.csv"])
        if missing:
            raise FileNotFoundError(f"Faltan archivos SCADA en {scada_dir}: " + ", ".join(missing))
        print(f"info: SCADA dir -> {scada_dir}")

        # Determinar pRTU (normalizar a 'zzz'; si auto y no se encuentra, NO filtrar)
        prtu_raw = (args.prtu or "").strip()
        prtu_value: Optional[str] = None
        if prtu_raw.lower() != "auto" and prtu_raw != "":
            prtu_value = prtu_raw.zfill(3) if prtu_raw.isdigit() else prtu_raw
        else:
            # intentar por checklist
            checklist_path = (args.checklist or "").strip()
            if not checklist_path:
                for pattern in ("CheckList_*.xlsx", "CheckList_*.xlsm"):
                    cands = glob.glob(os.path.join(outdir, pattern))
                    if cands:
                        cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        checklist_path = cands[0]
                        break
            if checklist_path and detect_prtu_from_checklist:
                try:
                    detect_val = detect_prtu_from_checklist(checklist_path)
                    if detect_val:
                        prtu_value = str(detect_val).zfill(3) if str(detect_val).isdigit() else str(detect_val)
                        wl.log_all("info", f"[SOE_MONARCH_V2] pRTU detectado (checklist): {prtu_value}", logger_console, logger)
                except Exception as exc:
                    wl.log_all("warning", f"[SOE_MONARCH_V2] No se pudo inferir pRTU desde checklist ({exc})", logger_console, logger)
            # intentar por estación
            if not prtu_value and args.station and detect_prtu_from_station:
                try:
                    detect_val2 = detect_prtu_from_station(args.station, scada_dir)
                    if detect_val2:
                        prtu_value = str(detect_val2).zfill(3) if str(detect_val2).isdigit() else str(detect_val2)
                        wl.log_all("info", f"[SOE_MONARCH_V2] pRTU detectado (estación): {prtu_value}", logger_console, logger)
                except Exception as exc:
                    wl.log_all("warning", f"[SOE_MONARCH_V2] No se pudo derivar pRTU desde estación ({exc})", logger_console, logger)

        # --- Cargar dataframes ---
        # 1) HIS
        df_soe = _read_csv(his_path, dtype={"osi_key": "string"})
        needed_his = {"time", "milli_secs", "state_text", "osi_key"}
        faltan_his = [c for c in needed_his if c not in df_soe.columns]
        if faltan_his:
            raise KeyError(f"El CSV HIS carece de columnas requeridas: {', '.join(faltan_his)}")

        df_soe["osi_key"] = df_soe["osi_key"].astype(str).str.strip()
        df_soe["milli_secs"] = pd.to_numeric(df_soe["milli_secs"], errors="coerce").fillna(0).astype(int).clip(0, 999)

        # 2) FEP_SCAN 32_10.csv -> IOA por Key
        df_fep = _read_csv(os.path.join(scada_dir, "32_10.csv"))
        # columnas necesarias
        for col in ("Key", "IntParms", "pRTU"):
            if col not in df_fep.columns:
                raise KeyError("32_10.csv debe contener columnas: Key, IntParms, pRTU.")

        # normalizaciones
        df_fep["Key"] = df_fep["Key"].astype(str).str.strip()
        df_fep["IntParms"] = pd.to_numeric(df_fep["IntParms"], errors="coerce").astype("Int64")
        df_fep["pRTU_raw"] = df_fep["pRTU"].astype(str).str.strip()
        df_fep["pRTU_norm"] = pd.to_numeric(df_fep["pRTU_raw"], errors="coerce")
        df_fep["pRTU_norm"] = df_fep["pRTU_norm"].round().astype("Int64")
        df_fep["pRTU_norm_str"] = df_fep["pRTU_norm"].astype(str).str.zfill(3)

        if prtu_value:
            base = prtu_value or ''
            strip_zero = prtu_value.lstrip('0') if prtu_value else ''
            norm_candidates = {
                base,
                base.zfill(3),
                strip_zero,
                strip_zero.zfill(3) if strip_zero else '000',
            }
            norm_candidates = {c for c in norm_candidates if c}
            if not norm_candidates:
                norm_candidates = {'000'}
            wl.log_all(
                "debug",
                f"[SOE_MONARCH_V2] Candidados pRTU para filtro: raw={prtu_value}, norm={norm_candidates}",
                logger_console,
                logger,
            )
            wl.log_all(
                "debug",
                f"[SOE_MONARCH_V2] Ejemplo pRTU en 32_10: {df_fep['pRTU_raw'].dropna().unique()[:10]}",
                logger_console,
                logger,
            )
            df_fep = df_fep[df_fep["pRTU_norm_str"].isin(norm_candidates)].copy()
            wl.log_all("info", f"[SOE_MONARCH_V2] Filtrado por pRTU={prtu_value}: {len(df_fep)} filas 32_10", logger_console, logger)
        else:
            wl.log_all("info", "[SOE_MONARCH_V2] pRTU auto no disponible: NO se filtra 32_10", logger_console, logger)

        # 3) SCADA_STATUS 10_4.csv -> pStates por Key
        df_status = _read_csv(os.path.join(scada_dir, "10_4.csv"), dtype={"Key": "string"})
        if "Key" not in df_status.columns or "pStates" not in df_status.columns:
            raise KeyError("10_4.csv debe contener columnas: Key, pStates.")
        df_status["Key"] = df_status["Key"].astype(str).str.strip()
        df_status["pStates"] = pd.to_numeric(df_status["pStates"], errors="coerce").astype("Int64")

        # 4) STATES_STATES 19_1.csv -> diccionario de states por #record
        df_states = _read_csv(os.path.join(scada_dir, "19_1.csv"))
        if "#record" not in df_states.columns:
            raise KeyError("19_1.csv debe contener la columna '#record'.")
        states_dict = _build_states_dict(df_states)

        # --- Enlaces (alineado con script standalone) ---
        wl.log_all("debug", f"[SOE_MONARCH_V2] HIS rows antes merge: {len(df_soe)}", logger_console, logger)
        wl.log_all("debug", f"[SOE_MONARCH_V2] 32_10 rows después filtro: {len(df_fep)}", logger_console, logger)
        df = df_soe.merge(
            df_fep[["Key", "IntParms"]],
            left_on="osi_key", right_on="Key", how="left"
        )
        df = df.rename(columns={"IntParms": "IOA"})
        df = df.drop(columns=["Key"])
        df = df.dropna(subset=["IOA"]).copy()

        wl.log_all("debug", f"[SOE_MONARCH_V2] Registros con IOA tras merge 32_10: {len(df)}", logger_console, logger)
        df = df.merge(
            df_status[["Key", "pStates"]],
            left_on="osi_key", right_on="Key", how="left"
        ).drop(columns=["Key"])

        def _map_event(row):
            rec = row.get("pStates")
            st_text = row.get("state_text")
            try:
                return states_dict.get(rec, {}).get("values", {}).get(str(st_text))
            except Exception:
                return None

        df["event"] = pd.to_numeric(df.apply(_map_event, axis=1), errors="coerce").astype("Int64")
        # Normalizar tiempo con milisegundos (evita concatenar si ya trae fracciones)
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df["time"] = df["time"] + pd.to_timedelta(df.get("milli_secs", 0).fillna(0).astype(int), unit="ms")
        df["time"] = df["time"].dt.strftime("%Y-%m-%d %H:%M:%S.%f").str.slice(0, -3)

        preferred = [
            "time", "milli_secs", "station_name", "point_name",
            "state_text", "event", "osi_key", "IOA",
            "timequality", "scanquality", "site_id", "pStates"
        ]
        cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
        df = df[cols]

        out_csv = os.path.join(outdir, "SOE_Monarch.csv")
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")

        wl.log_all("info", f"[SOE_MONARCH_V2] Filas salida: {len(df)}", logger_console, logger)
        wl.log_all("info", f"[SOE_MONARCH_V2] Generado: {out_csv}", logger_console, logger)
        print(out_csv)
        print("info: SOE_Monarch.csv generado correctamente.")
        out_csv = os.path.join(outdir, "SOE_Monarch.csv")
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")

        wl.log_all("info", f"[SOE_MONARCH_V2] Filas salida: {len(df)}", logger_console, logger)
        wl.log_all("info", f"[SOE_MONARCH_V2] Generado: {out_csv}", logger_console, logger)
        print(out_csv)  # <- la UI puede capturar esta ruta
        print("info: SOE_Monarch.csv generado correctamente.")

    except Exception as e:
        wl.log_all("error", f"[SOE_MONARCH_V2] Error: {e}", logger_console, logger)
        print(f"error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
