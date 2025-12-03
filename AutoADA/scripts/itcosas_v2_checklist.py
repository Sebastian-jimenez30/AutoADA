# -*- coding: utf-8 -*-
"""
Checklist (v2): cruza SOE_Local (v2) + SOE_Monarch (v2) con el CheckList de STATUS y genera SOE_completo.xlsx.

Uso (CLI):
  python -m scripts.itcosas_v2_checklist --checklist=<ruta.xlsx> --soe-local=<ruta.csv> --soe-monarch=<ruta.csv> [--outdir=<dir>] [--sheet-status STATUS] [--sheet-soe SOE] [--tolerancia-ms 3] [--abrir-excel]

Por defecto busca salidas en out/pruebas/ (junto al .exe). Imprime la ruta del Excel generado.
"""

import os
import sys
import glob
import argparse
import subprocess
import unicodedata
from typing import Optional, List, Dict

import numpy as np

# pandas / openpyxl requeridos
try:
    import pandas as pd
except Exception:
    print("error: No se pudo importar pandas. Instálalo con 'pip install pandas'.")
    raise
try:
    from openpyxl import load_workbook
except Exception:
    print("error: No se pudo importar openpyxl. Instálalo con 'pip install openpyxl'.")
    raise

# Rutas del proyecto (tolerante a dev/pyinstaller)
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


# -----------------------------
# CLI
# -----------------------------
def _args():
    p = argparse.ArgumentParser(description="Checklist v2 — cruza SOE_Local + SOE_Monarch con STATUS.")
    p.add_argument("--checklist", type=str, default=None, help="Ruta al archivo de checklist (.xlsx/.xlsm).")
    # aceptar alias con - y _
    p.add_argument("--soe-local", "--soe_local", dest="soe_local", type=str, default=None,
                   help="Ruta a SOE_Local.csv.")
    p.add_argument("--soe-monarch", "--soe_monarch", dest="soe_monarch", type=str, default=None,
                   help="Ruta a SOE_Monarch.csv.")
    p.add_argument("--outdir", type=str, default=None, help="Carpeta de salida (default: out/pruebas).")
    p.add_argument("--sheet-status", type=str, default="STATUS", help="Nombre de la hoja STATUS.")
    p.add_argument("--sheet-soe", type=str, default="SOE", help="Nombre de la hoja SOE.")
    p.add_argument("--tolerancia-ms", type=int, default=3, help="Tolerancia de matching en ms (default: 3).")
    p.add_argument("--abrir-excel", action="store_true", help="Abrir el Excel al finalizar.")
    return p.parse_args()


# -----------------------------
# Helpers
# -----------------------------
def _read_csv(path: str, **kwargs) -> "pd.DataFrame":
    last = None
    for enc in ("utf-8", "utf-8-sig", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except Exception as e:
            last = e
    raise RuntimeError(f"No se pudo leer '{path}' (último error: {last})")

def _find_first(patterns: List[str], base_dir: str) -> Optional[str]:
    for pat in patterns:
        cands = glob.glob(os.path.join(base_dir, pat))
        if cands:
            # prioriza el más reciente
            cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return cands[0]
    return None

def _open_file(path: str):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass

def _fmt_time_mmm(dt: "pd.Timestamp") -> str:
    # Si viene NaT, devuelve vacío
    if pd.isna(dt):
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # milisegundos


def _normalize_header(col: str) -> str:
    if col is None:
        return ""
    # Remover acentos, espacios, guiones y subrayados, y bajar a minúsculas
    nfkd = unicodedata.normalize("NFKD", str(col))
    no_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return (
        no_accents.replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .lower()
    )


def _map_checklist_columns(df_checklist: "pd.DataFrame") -> "pd.DataFrame":
    aliases: Dict[str, str] = {
        "ioa": "IOA",
        "scadakey": "SCADAkey",
        "scadakey2": "SCADAkey",  # por si vienen sufijos
        "scadakey1": "SCADAkey",
        "scadakeyv2": "SCADAkey",
        "scadakeys": "SCADAkey",
        "scadakey_": "SCADAkey",
        "aor": "AOR",
        "type": "type",
        "station": "Station",
        "estacion": "Station",
        "name": "Name",
        "prueba": "Prueba",
    }

    mapping: Dict[str, str] = {}
    for col in df_checklist.columns:
        norm = _normalize_header(col)
        if norm in aliases and aliases[norm] not in mapping.values():
            mapping[col] = aliases[norm]

    required = ["IOA", "SCADAkey", "AOR", "type", "Station", "Name", "Prueba"]
    missing = [req for req in required if req not in mapping.values()]
    if missing:
        raise KeyError(
            f"Error: Faltan columnas requeridas ({', '.join(missing)}) en {','.join(df_checklist.columns)}"
        )

    return df_checklist.rename(columns=mapping)[required]


def _delete_temp(path: str):
    try:
        base = os.path.basename(path)
        if base.startswith("tmp") and "pruebas_inputs" in os.path.abspath(path).replace("\\", "/"):
            os.remove(path)
    except Exception:
        pass


def _load_checklist_dataframe(path: str, preferred_sheet: str | None, required_cols: List[str]) -> "pd.DataFrame":
    """
    Lee el checklist buscando la primera hoja que contenga las columnas requeridas (tolerante a aliases).
    Prioriza `preferred_sheet` y luego recorre el resto.
    """
    dtype_dict_checklist = {"SCADAkey": str}
    try:
        excel = pd.ExcelFile(path, engine="openpyxl")
        sheet_names = excel.sheet_names
    except Exception:
        # fallback: intenta solo con preferred_sheet
        sheet_names = [preferred_sheet] if preferred_sheet else []

    seen: set[str] = set()
    candidates: List[str] = []
    if preferred_sheet:
        candidates.append(preferred_sheet)
        seen.add(preferred_sheet)
    for s in sheet_names:
        if s not in seen:
            candidates.append(s)
            seen.add(s)

    last_err: Exception | None = None
    for sheet in candidates:
        try:
            df_raw = pd.read_excel(path, sheet_name=sheet, dtype=dtype_dict_checklist, engine="openpyxl")
            df_norm = _map_checklist_columns(df_raw)
            # asegurar que están las requeridas en el resultado
            missing = [c for c in required_cols if c not in df_norm.columns]
            if not missing:
                return df_norm
        except Exception as exc:  # guarda y sigue probando otras hojas
            last_err = exc
            continue

    # Si no encontró ninguna hoja válida, propaga el último error o uno nuevo descriptivo
    cols = []
    try:
        cols = list(df_raw.columns)  # type: ignore[name-defined]
    except Exception:
        pass
    if last_err:
        raise KeyError(f"Error: Faltan columnas requeridas ({', '.join(required_cols)}) en {','.join(cols) or 'la(s) hoja(s) revisada(s)'}") from last_err
    raise KeyError(f"Error: No se encontró una hoja con columnas {', '.join(required_cols)} en {os.path.basename(path)}")


# -----------------------------
# Main
# -----------------------------
def main():
    args = _args()

    outdir = args.outdir or os.path.join(output_root(), "out", "pruebas")
    os.makedirs(outdir, exist_ok=True)

    # Logger
    log_dir = os.path.join(output_root(), "log")
    os.makedirs(log_dir, exist_ok=True)
    logger, logger_console = Logger.initlog(os.path.join(log_dir, "pruebas.log"))
    wl = Logger.write_log()

    try:
        base_dir = outdir  # usar outdir como base para defaults
        temp_inputs: list[str] = []

        # Resolver rutas por defecto si no se pasaron
        checklist_path = args.checklist or _find_first(["CheckList_*.xlsx", "CheckList_*.xlsm"], base_dir)
        if not checklist_path or not os.path.isfile(checklist_path):
            raise FileNotFoundError("No se encontró el archivo de checklist (intenta --checklist=...).")
        if os.path.basename(checklist_path).startswith("tmp"):
            temp_inputs.append(checklist_path)

        soe_local_path = args.soe_local or os.path.join(base_dir, "SOE_Local.csv")
        if not os.path.isfile(soe_local_path):
            raise FileNotFoundError("No se encontró SOE_Local.csv (intenta --soe-local=...).")

        soe_monarch_path = args.soe_monarch or os.path.join(base_dir, "SOE_Monarch.csv")
        if not os.path.isfile(soe_monarch_path):
            raise FileNotFoundError("No se encontró SOE_Monarch.csv (intenta --soe-monarch=...).")

        wl.log_all("info", f"[CHECKLIST_V2] checklist={checklist_path}", logger_console, logger)
        wl.log_all("info", f"[CHECKLIST_V2] soe_local={soe_local_path}", logger_console, logger)
        wl.log_all("info", f"[CHECKLIST_V2] soe_monarch={soe_monarch_path}", logger_console, logger)

        # ----------------- Cargar SOE_Local (v2) -----------------
        df_soe_local = _read_csv(soe_local_path)
        if "IOA" not in df_soe_local.columns:
            raise KeyError("SOE_Local.csv debe contener la columna 'IOA'.")
        # excluir NaN IOA y convertir
        if "Event" in df_soe_local.columns:
            df_soe_local = df_soe_local[df_soe_local["Event"] != -1]
        df_soe_local = df_soe_local[df_soe_local["IOA"].notna()].copy()
        df_soe_local["IOA"] = pd.to_numeric(df_soe_local["IOA"], errors="coerce").astype("Int64")
        # sufijos _local
        df_soe_local = df_soe_local.add_suffix("_local")
        df_soe_local["IOA_local"] = pd.to_numeric(df_soe_local["IOA_local"], errors="coerce").astype("Int64")

        # ----------------- Cargar SOE_Monarch (v2) -----------------
        df_soe_monarch = _read_csv(soe_monarch_path, dtype={"osi_key": "string"})
        if "time" not in df_soe_monarch.columns or "IOA" not in df_soe_monarch.columns:
            raise KeyError("SOE_Monarch.csv debe contener columnas 'time' e 'IOA'.")
        df_soe_monarch["IOA"] = pd.to_numeric(df_soe_monarch["IOA"], errors="coerce").astype("Int64")
        # eliminar duplicados time+IOA (igual que el suelto)
        df_soe_monarch = df_soe_monarch.drop_duplicates(subset=["time", "IOA"]).copy()
        # sufijos _monarch
        df_soe_monarch = df_soe_monarch.add_suffix("_monarch")

        # ----------------- Cargar Checklist (STATUS) -----------------
        required_cols = ["IOA", "SCADAkey", "AOR", "type", "Station", "Name", "Prueba"]
        df_checklist = _load_checklist_dataframe(checklist_path, args.sheet_status, required_cols)

        # IOA como enteros (nullable)
        df_checklist = df_checklist[df_checklist["IOA"].notna()].copy()
        df_checklist["IOA"] = pd.to_numeric(df_checklist["IOA"], errors="coerce").astype("Int32")

        # ----------------- Indicadores presencia en SE -----------------
        df_checklist["IOA_in_SE"] = df_checklist["IOA"].isin(df_soe_local["IOA_local"])
        total_ioa = len(df_checklist["IOA"])
        encontrados = int(df_checklist["IOA_in_SE"].sum())
        print(f"Hay {total_ioa} IOA en {os.path.basename(checklist_path)}\nSe encontraron {encontrados} IOA en el archivo SOE_Local.csv\n")

        if encontrados < total_ioa:
            ioa_no = df_checklist[~df_checklist["IOA_in_SE"]]["IOA"]
            print(f"No se encontraron {total_ioa - encontrados} IOA en el archivo: SOE_Local.csv")
            print(f"IOA no encontradas en el archivo SOE_Local.csv:")
            print(list(ioa_no.values))
            print("")

        # Validación rápida (como suelto): al menos un IOA > 0
        if not (df_soe_local["IOA_local"] > 0).any():
            print("No hay eventos con envio a nivel 3 en el archivo de SOE_Local.csv.\n")
            sys.exit(2)
        else:
            print("SOE_Local.csv correcto...\n")

        # ----------------- Matching con tolerancia (idéntico al suelto, con fallback) -----------------
        tol = pd.Timedelta(milliseconds=int(args.tolerancia_ms))
        tol_fallback = pd.Timedelta(milliseconds=max(int(args.tolerancia_ms), 50))

        # asegurar tiempos como datetime
        df_soe_local["time_local"] = pd.to_datetime(df_soe_local["time_local"], errors="coerce")
        df_soe_monarch["time_monarch"] = pd.to_datetime(df_soe_monarch["time_monarch"], errors="coerce")

        resultados_combinados = []
        ioa_checklist = df_checklist["IOA"].unique()

        # Columnas locales usadas en el suelto
        cols_local = [
            "time_local", "milli_secs_local", "Tension_local", "Bahia_local",
            "Name_SE_local", "Name_Monarch_local", "IOA_local", "Event_local"
        ]
        # Asegurar que existan, si no existen se crearán vacías para no romper
        for c in cols_local:
            if c not in df_soe_local.columns:
                df_soe_local[c] = "" if c != "IOA_local" else pd.NA

        def _build_matches(tolerance: "pd.Timedelta") -> list["pd.DataFrame"]:
            matches: list["pd.DataFrame"] = []
            for ioa in ioa_checklist:
                df_loc_l = df_soe_local[df_soe_local["IOA_local"] == ioa][cols_local]
                df_loc_m = df_soe_monarch[df_soe_monarch["IOA_monarch"] == ioa]
                if df_loc_l.empty or df_loc_m.empty:
                    continue
                for _, row_local in df_loc_l.iterrows():
                    for _, row_monarch in df_loc_m.iterrows():
                        diff = row_local["time_local"] - row_monarch["time_monarch"]
                        if pd.isna(diff):
                            continue
                        if abs(diff) <= tolerance:
                            combined_row = pd.DataFrame(
                                [row_local.values.tolist() + row_monarch.values.tolist()],
                                columns=row_local.index.tolist() + row_monarch.index.tolist()
                            )
                            matches.append(combined_row)
            return matches

        resultados_combinados = _build_matches(tol)
        if not resultados_combinados:
            print("info: Sin coincidencias con la tolerancia base, probando fallback de 50 ms...")
            resultados_combinados = _build_matches(tol_fallback)

        if resultados_combinados:
            df_soe_comb = pd.concat(resultados_combinados, ignore_index=True)
        else:
            print("No se encontraron coincidencias dentro de la tolerancia para ninguna IOA. El DataFrame combinado estará vacío.")
            df_soe_comb = pd.DataFrame()

        # ----------------- VALIDACIONES (idénticas al suelto) -----------------
        if not df_soe_comb.empty:
            # 0: IOA_local == IOA_monarch
            validacion_0 = df_soe_comb["IOA_local"] == df_soe_comb["IOA_monarch"]

            # 1: Event_local == event_monarch
            if "event_monarch" not in df_soe_comb.columns:
                df_soe_comb["event_monarch"] = -999
            validacion_1 = df_soe_comb["Event_local"] == df_soe_comb["event_monarch"]

            # 2: timequality_monarch == 0
            if "timequality_monarch" not in df_soe_comb.columns:
                df_soe_comb["timequality_monarch"] = -999
            validacion_2 = (df_soe_comb["timequality_monarch"] == 0)

            # 3: scanquality_monarch == 0
            if "scanquality_monarch" not in df_soe_comb.columns:
                df_soe_comb["scanquality_monarch"] = -999
            validacion_3 = (df_soe_comb["scanquality_monarch"] == 0)

            # 4: Name (Name_Monarch_local vs point_name_monarch)
            if "point_name_monarch" not in df_soe_comb.columns:
                df_soe_comb["point_name_monarch"] = ""
            if "Name_Monarch_local" not in df_soe_comb.columns:
                df_soe_comb["Name_Monarch_local"] = ""
            validacion_4 = df_soe_comb["Name_Monarch_local"] == df_soe_comb["point_name_monarch"]

            df_soe_comb["valido"] = np.select(
                [
                    validacion_0 & validacion_1 & validacion_2 & validacion_3,  # & validacion_4,
                    ~validacion_0,
                    ~validacion_1,
                    ~validacion_2,
                    ~validacion_3,
                    ~validacion_4
                ],
                ["Good", "IOA", "event", "timequality", "scanquality", "Name"],
                default="Other"
            )

            # Formateo de tiempos a .mmm para Excel
            df_soe_comb["time_local"] = pd.to_datetime(df_soe_comb["time_local"])
            df_soe_comb["time_monarch"] = pd.to_datetime(df_soe_comb["time_monarch"])
            df_soe_comb["time_local"] = df_soe_comb["time_local"].apply(_fmt_time_mmm)
            df_soe_comb["time_monarch"] = df_soe_comb["time_monarch"].apply(_fmt_time_mmm)

            # Métricas por IOA (exactamente como el suelto)
            df_checklist["IOA_SOE"] = df_checklist["IOA"].apply(
                lambda x: df_soe_comb["IOA_monarch"].eq(x).sum()
            ).astype(int)

            df_checklist["IOA_validadas"] = df_checklist.apply(
                lambda row: df_soe_comb[
                    (df_soe_comb["IOA_monarch"] == row["IOA"]) &
                    (df_soe_comb["valido"] == "Good")
                ].shape[0],
                axis=1
            ).astype(int)

            df_checklist.loc[df_checklist["IOA_validadas"] >= 1, "Prueba"] = "Good"
            df_checklist.loc[df_checklist["IOA_validadas"] < 1, "Prueba"] = "No probado"
        else:
            # Hoja SOE vacía, igual exportamos
            df_checklist["IOA_SOE"] = 0
            df_checklist["IOA_validadas"] = 0
            df_checklist.loc[df_checklist["IOA_validadas"] >= 1, "Prueba"] = "Good"
            df_checklist.loc[df_checklist["IOA_validadas"] < 1, "Prueba"] = "No probado"

        # ----------------- Guardar Excel -----------------
        out_xlsx = os.path.join(outdir, "SOE_completo.xlsx")
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
            # STATUS
            df_checklist.to_excel(writer, index=False, sheet_name=args.sheet_status)
            ws_status = writer.sheets[args.sheet_status]
            ws_status.auto_filter.ref = ws_status.dimensions
            ws_status.freeze_panes = "A2"

            # SOE combinado
            df_soe_comb.to_excel(writer, index=False, sheet_name=args.sheet_soe)
            ws_soe = writer.sheets[args.sheet_soe]
            ws_soe.auto_filter.ref = ws_soe.dimensions
            ws_soe.freeze_panes = "A2"

        print(out_xlsx)  # la UI captura esta ruta
        print("info: SOE_completo.xlsx generado.")

        if getattr(args, "abrir_excel", False):
            _open_file(out_xlsx)

    except Exception as e:
        wl.log_all("error", f"[CHECKLIST_V2] Error: {e}", logger_console, logger)
        print(f"error: {e}")
        sys.exit(1)
    finally:
        for tmp in temp_inputs if 'temp_inputs' in locals() else []:
            _delete_temp(tmp)


if __name__ == "__main__":
    main()
