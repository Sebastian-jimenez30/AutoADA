# scripts/pyp_soe_monarch.py
import argparse
import os
import sys
import re
import pandas as pd
from typing import Optional, Tuple, List


def _ensure_out_pruebas() -> str:
    root = os.getcwd()
    outdir = os.path.join(root, "out", "pruebas")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _scada_dir(empresa: str) -> str:
    # SCADA generado por la app: out/<empresa>/SCADA
    return os.path.join(os.getcwd(), "out", empresa, "SCADA")


def _read_csv_robust(path, **kwargs):
    """
    Lee CSV intentando primero con coma y luego con ';' si falla.
    """
    try:
        return pd.read_csv(path, **kwargs)
    except Exception:
        return pd.read_csv(path, sep=';', **kwargs)


def _extraer_prtu_desde_checklist(path_xlsm: str) -> str:
    """
    Lee hojas STATUS y ANALOG; toma columna 'SCADAkey' (case-insensitive) o, si no existe,
    la columna B. De cada key (formato xx-xxx-xxx), se eliminan '-' y se toman
    los dígitos [2:5] como pRTU. Si hay varios, se escoge el más frecuente.
    Retorna siempre en 3 dígitos (zfill).
    """
    if not os.path.isfile(path_xlsm):
        raise FileNotFoundError(f"No existe checklist: {path_xlsm}")

    print(">> [SOE_MONARCH] Abriendo checklist (.xlsm)…")
    xls = pd.ExcelFile(path_xlsm, engine="openpyxl")
    print(f">> [SOE_MONARCH] Hojas encontradas: {xls.sheet_names}")

    keys: List[str] = []
    for hoja in ("STATUS", "ANALOG"):
        if hoja not in xls.sheet_names:
            print(f">> [SOE_MONARCH] Hoja no presente: {hoja} (se ignora)")
            continue

        print(f">> [SOE_MONARCH] Leyendo hoja: {hoja}")
        df = pd.read_excel(xls, sheet_name=hoja, dtype=str, engine="openpyxl")

        lower_map = {str(c).strip().lower(): c for c in df.columns}
        if "scadakey" in lower_map:
            colname = lower_map["scadakey"]
            serie = df[colname]
        else:
            try:
                serie = df.iloc[:, 1]  # fallback: columna B
                print(">> [SOE_MONARCH] Columna 'SCADAkey' no encontrada; usando columna B como fallback.")
            except Exception:
                print(">> [SOE_MONARCH] No fue posible usar columna B en esta hoja.")
                continue

        for val in serie.dropna().astype(str):
            s = re.sub(r"[^0-9]", "", val)
            if len(s) >= 8:
                prtu = s[:8][2:5]
                if prtu.isdigit():
                    keys.append(prtu)

    if not keys:
        raise ValueError("No se pudieron extraer SCADAkey válidas del checklist para calcular pRTU.")

    prtu_series = pd.Series(keys)
    prtu_mode = prtu_series.mode().iloc[0]
    return str(prtu_mode).zfill(3)


def _prtu_from_station(station: str, scada_dir: str) -> Optional[str]:
    station = (station or "").strip()
    if not station:
        return None

    # Si viene como "89: ESME000", usamos el número directamente
    if ':' in station:
        prefix, suffix = station.split(':', 1)
        prefix = prefix.strip()
        if prefix.isdigit():
            return prefix.zfill(3)
        station = suffix.strip()

    path_32_6 = os.path.join(scada_dir, '32_6.csv')
    if not os.path.isfile(path_32_6):
        print(f"[SOE_MONARCH] 32_6.csv no encontrado en {scada_dir}; se omitirá lookup por RTU.")
        digits = re.sub(r"[^0-9]", "", station)
        return digits.zfill(3) if digits else None

    df = _read_csv_robust(path_32_6, dtype=str)
    if df.empty:
        return None

    df_cols = {str(c).strip().lower(): c for c in df.columns}
    record_col = df_cols.get('#record') or df_cols.get('record')
    if not record_col:
        for key, col in df_cols.items():
            if 'record' in key:
                record_col = col
                break
    name_col = df_cols.get('name')

    def normalize_record(raw: str) -> Optional[str]:
        if not raw:
            return None
        digits = re.sub(r"[^0-9]", "", str(raw))
        return digits.zfill(3) if digits else None

    target_upper = station.strip().upper()
    if name_col:
        mask = df[name_col].astype(str).str.strip().str.upper() == target_upper
        if mask.any() and record_col:
            rec_val = df.loc[mask, record_col].astype(str).iloc[0]
            norm = normalize_record(rec_val)
            if norm:
                return norm

    digits = normalize_record(station)
    if digits:
        return digits

    return None


def _normalize_states_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza cabeceras y detecta/renombra la columna 'record' en 19_1.
    También normaliza variantes de 'names_*' y permite '#record' como alias.
    """
    orig_cols = list(df.columns)
    df = df.copy()

    # Preservar '#record' si existiera, pero normalizar el resto
    cols_norm = []
    record_alias_found = None
    for c in df.columns:
        c_str = str(c).strip()
        if c_str.lower() in ("#record", "record", "precord", "p_record", "rec", "registro"):
            record_alias_found = c
        c_norm = c_str.lower().replace(" ", "_").replace("-", "_")
        cols_norm.append(c_norm)
    df.columns = cols_norm

    print(f">> [SOE_MONARCH] 19_1 columnas detectadas (normalizadas): {list(df.columns)}")
    if orig_cols != list(df.columns):
        print(f">> [SOE_MONARCH] 19_1 columnas originales: {orig_cols}")

    # Mapear alias comunes de 'record'
    aliases_record = ["#record", "record", "precord", "p_record", "rec", "registro"]
    record_col = None
    # búsqueda exacta tras normalización
    for c in df.columns:
        if c in ("#record", "record"):
            record_col = c
            break
    if not record_col:
        for c in df.columns:
            if c in aliases_record:
                record_col = c
                break

    # Heurística si aún no aparece
    if not record_col:
        for c in df.columns:
            serie = pd.to_numeric(df[c], errors="coerce")
            if serie.notna().mean() > 0.8 and serie.nunique(dropna=True) > 5:
                record_col = c
                print(f">> [SOE_MONARCH] 19_1: infiriendo '{record_col}' como columna 'record'.")
                break

    if not record_col:
        raise ValueError("19_1 no trae una columna 'record' reconocible. Revisa encabezados/separador.")

    if record_col != "record":
        df = df.rename(columns={record_col: "record"})

    # Normalizar variantes names*, name_*
    rename_map = {}
    for c in list(df.columns):
        m = re.match(r"^names?_?(\d+)$", c)
        if m:
            idx = m.group(1)
            rename_map[c] = f"names_{idx}"
    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def _build_states_dict(df_states: pd.DataFrame) -> dict:
    """
    Construye diccionario: record -> { 'description': ..., 'values': { nombre_estado: indice } }
    Espera columnas: 'record','description','names_0'...'names_n' (rango flexible).
    """
    dic = {}
    name_cols = [c for c in df_states.columns if str(c).startswith("names_")]
    name_cols_sorted = sorted(
        name_cols,
        key=lambda c: int(str(c).split("_")[1]) if str(c).split("_")[1].isdigit() else 9999,
    )

    print(f">> [SOE_MONARCH] 19_1 columnas de estados encontradas: {name_cols_sorted}")

    for _, row in df_states.iterrows():
        rec = row.get("record", None)
        if pd.isna(rec):
            continue
        values_map = {}
        for nc in name_cols_sorted:
            val = row.get(nc, None)
            if pd.isna(val):
                continue
            # índice = número en el sufijo del nombre
            idx = int(nc.split("_")[1]) if "_" in nc and str(nc.split("_")[1]).isdigit() else None
            values_map[str(val)] = idx
        if values_map:
            dic[rec] = {
                "description": row.get("description", None),
                "values": values_map,
            }
    print(f">> [SOE_MONARCH] Diccionario de estados construido. Registros: {len(dic)}")
    return dic


def _select_his_file(his_input: str, base_prefix: str = "data-") -> str:
    """
    Selecciona el archivo HIS (data-*.csv) conservando el contrato del primer script:
    - Si his_input es ruta a archivo: usarlo tal cual.
    - Si his_input es ruta a carpeta: buscar exactamente un 'data-*.csv'.
    - Si his_input == 'AUTO' (case-insensitive): buscar en CWD un único 'data-*.csv'.
    """
    his_input = (his_input or "").strip()
    if os.path.isfile(his_input):
        return his_input

    if his_input.upper() == "AUTO":
        search_dir = os.getcwd()
    elif os.path.isdir(his_input):
        search_dir = his_input
    else:
        # Mantener comportamiento anterior: tratarlo como archivo (fallará abajo si no existe)
        return his_input

    candidatos = [f for f in os.listdir(search_dir) if f.startswith(base_prefix) and f.lower().endswith(".csv")]
    if len(candidatos) == 1:
        elegido = os.path.join(search_dir, candidatos[0])
        print(f">> [SOE_MONARCH] HIS auto-detectado: {elegido}")
        return elegido
    elif len(candidatos) == 0:
        raise FileNotFoundError(f"No se encontró ningún '{base_prefix}*.csv' en {search_dir}")
    else:
        raise RuntimeError(f"Se encontraron múltiples '{base_prefix}*.csv' en {search_dir}: {candidatos}. Deja solo uno o especifica la ruta exacta.")


def main():
    parser = argparse.ArgumentParser(
        description="Generar SOE_Monarch.csv usando SCADA (32_10,10_4,19_1), checklist y data-*.csv"
    )
    parser.add_argument("empresa", type=str, help="Empresa (p.ej. INTERCOLOMBIA)")
    parser.add_argument("checklist_path", type=str, help="Ruta al checklist .xlsm (para inferir pRTU)")
    parser.add_argument("his_data_path", type=str, help="Ruta al archivo HIS (data-*.csv), carpeta o 'AUTO'")
    parser.add_argument("--station", default=None, help="Código RTU/SAS (p.ej. ESME000 o '89: ESME000')")
    parser.add_argument("--his-base", default="data-", help="Prefijo para auto-detección del HIS (por defecto 'data-')")
    args = parser.parse_args()

    out_pruebas = _ensure_out_pruebas()
    scada_dir = _scada_dir(args.empresa)

    # 0) Selección de archivo HIS (soporta archivo directo, carpeta o 'AUTO')
    try:
        his_path = _select_his_file(args.his_data_path, base_prefix=args.his_base)
    except Exception as e:
        print(f"[SOE_MONARCH ERROR] HIS: {e}")
        sys.exit(1)

    # 1) pRTU desde checklist (se prioriza checklist para conservar lógica original)
    print(">> [SOE_MONARCH] Extrayendo pRTU desde checklist…")
    try:
        pRTU = _extraer_prtu_desde_checklist(args.checklist_path)  # '040', '075', etc.
        print(f">> [SOE_MONARCH] pRTU detectado (checklist): {pRTU}")
    except Exception as e:
        print(f"[SOE_MONARCH WARN] No se pudo inferir pRTU desde checklist: {e}")
        # Fallback opcional: intentar con --station si viene
        if args.station:
            pRTU = _prtu_from_station(args.station, scada_dir) or None
            if pRTU:
                print(f">> [SOE_MONARCH] pRTU derivado desde station: {pRTU}")
        if not pRTU:
            print("[SOE_MONARCH ERROR] No fue posible determinar pRTU (checklist/station).")
            sys.exit(1)

    # 2) Cargar SCADA
    fep_scan_path = os.path.join(scada_dir, "32_10.csv")
    scada_status_path = os.path.join(scada_dir, "10_4.csv")
    states_states_path = os.path.join(scada_dir, "19_1.csv")

    for req in (fep_scan_path, scada_status_path, states_states_path):
        if not os.path.isfile(req):
            print(f"[SOE_MONARCH ERROR] No existe {req}")
            sys.exit(1)

    print(">> [SOE_MONARCH] Leyendo 32_10 (FEP_SCAN)…")
    df_fep = _read_csv_robust(fep_scan_path)
    if "pRTU" in df_fep.columns:
        # normalizar pRTU como str de 3 dígitos
        df_fep["pRTU_str"] = (
            df_fep["pRTU"]
            .astype("Int64", errors="ignore")
            .astype(str)
            .str.replace(".0", "", regex=False)
        )
        df_fep["pRTU_str"] = df_fep["pRTU_str"].str.replace(r"\.0$", "", regex=True).str.zfill(3)
    else:
        print("[SOE_MONARCH ERROR] 32_10.csv no contiene columna 'pRTU'.")
        sys.exit(1)

    # Filtrar por pRTU
    df_fep = df_fep[df_fep["pRTU_str"] == pRTU]
    if df_fep.empty:
        print(f"[SOE_MONARCH WARN] 32_10.csv no tiene registros para pRTU={pRTU}.")
    # Validar columnas para IOA
    if not {"Key", "IntParms"}.issubset(df_fep.columns):
        print("[SOE_MONARCH ERROR] 32_10.csv debe contener columnas 'Key' y 'IntParms'.")
        sys.exit(1)
    df_fep = df_fep[["Key", "IntParms"]].copy()
    df_fep["IntParms"] = pd.to_numeric(df_fep["IntParms"], errors="coerce").astype("Int64")

    print(">> [SOE_MONARCH] Leyendo 10_4 (SCADA_STATUS)…")
    df_status = _read_csv_robust(scada_status_path, dtype={"Key": "str"})
    if "pStates" not in df_status.columns or "Key" not in df_status.columns:
        print("[SOE_MONARCH ERROR] 10_4.csv debe contener columnas 'Key' y 'pStates'.")
        sys.exit(1)
    df_status["pStates"] = pd.to_numeric(df_status["pStates"], errors="coerce").astype("Int64")

    print(">> [SOE_MONARCH] Leyendo 19_1 (STATES_STATE)…")
    df_states_raw = _read_csv_robust(states_states_path)
    try:
        df_states = _normalize_states_df(df_states_raw)
    except Exception as e:
        print(f"[SOE_MONARCH ERROR] 19_1: {e}")
        sys.exit(1)

    if "record" not in df_states.columns:
        print("[SOE_MONARCH ERROR] 19_1 no tiene columna 'record' (ni alias reconocible).")
        sys.exit(1)

    states_dict = _build_states_dict(df_states)

    # 3) Cargar HIS data-*.csv (archivo seleccionado)
    if not os.path.isfile(his_path):
        print(f"[SOE_MONARCH ERROR] No existe HIS data en {his_path}")
        sys.exit(1)

    print(">> [SOE_MONARCH] Leyendo HIS data…")
    df_his = _read_csv_robust(his_path, dtype={"osi_key": "str"})
    needed_cols = {"osi_key", "time", "milli_secs", "state_text"}
    missing = [c for c in needed_cols if c not in df_his.columns]
    if missing:
        print(f"[SOE_MONARCH WARN] HIS data no contiene columnas esperadas {missing}. Se continuará con lo disponible.")

    # 4) Merge con FEP (para IOA)
    print(">> [SOE_MONARCH] Combinando con 32_10 (IOA)…")
    df = df_his.merge(df_fep, left_on="osi_key", right_on="Key", how="left")
    if "IntParms" in df.columns:
        df = df.rename(columns={"IntParms": "IOA"})
    else:
        print("[SOE_MONARCH ERROR] No se pudo derivar 'IOA' desde 32_10 (IntParms).")
        sys.exit(1)
    df = df.drop(columns=["Key"], errors="ignore")
    df = df.dropna(subset=["IOA"])

    # 5) Merge con STATUS (pStates)
    print(">> [SOE_MONARCH] Combinando con 10_4 (pStates)…")
    df = df.merge(df_status[["Key", "pStates"]], left_on="osi_key", right_on="Key", how="left")
    df = df.drop(columns=["Key"], errors="ignore")

    # 6) Derivar 'event' con diccionario de 19_1
    print(">> [SOE_MONARCH] Derivando columna 'event'…")

    def _map_event(row):
        pst = row.get("pStates", None)
        st_text = row.get("state_text", None)
        if pd.isna(pst) or pd.isna(st_text):
            return None
        rec = states_dict.get(pst, None)
        if not rec:
            return None
        # state_text llega como str; en 19_1 guardamos {nombre_estado: índice}
        return rec["values"].get(str(st_text), None)

    df["event"] = df.apply(_map_event, axis=1)

    # 7) Armar time con milli_secs
    if "time" in df.columns and "milli_secs" in df.columns:
        ms = pd.to_numeric(df["milli_secs"], errors="coerce").fillna(0).astype(int).astype(str).str.zfill(3)
        df["time"] = df["time"].astype(str) + "." + ms

    # 8) Guardar salida
    out_csv = os.path.join(out_pruebas, "SOE_Monarch.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print(f">> [SOE_MONARCH] Generado: {out_csv}")
    print(">> [SOE_MONARCH] ¡Listo!")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[SOE_MONARCH ERROR] no controlado: {e}")
        sys.exit(1)
