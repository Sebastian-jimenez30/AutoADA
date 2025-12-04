# scripts/pyp_checklist.py
import argparse
import os
import sys
import pandas as pd
import numpy as np
import subprocess


def _out_pruebas(root: str | None = None) -> str:
    base = root or os.getcwd()
    outdir = os.path.join(base, "out", "pruebas")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _read_csv_robust(path, **kwargs):
    try:
        return pd.read_csv(path, **kwargs)
    except Exception:
        return pd.read_csv(path, sep=";", **kwargs)


def _log(msg: str, tag: str = "INFO"):
    print(f"[CHECKLIST {tag}] {msg}")


def main():
    parser = argparse.ArgumentParser(
        description="Consolidar resultados: Direcciones + SOE_Local + SOE_Monarch + Checklist -> SOE_completo.xlsx"
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=None,
        help="Carpeta de salida/entrada para archivos de pruebas (por defecto: ./out/pruebas)",
    )
    parser.add_argument(
        "--checklist",
        type=str,
        required=True,
        help="Ruta al archivo de checklist (.xlsx/.xlsm). Se leerá la hoja STATUS.",
    )
    parser.add_argument(
        "--abrir-excel",
        action="store_true",
        help="Abre el Excel generado con la aplicación por defecto (Windows).",
    )
    parser.add_argument(
        "--sheet-status",
        type=str,
        default="STATUS",
        help="Nombre de la hoja del checklist para STATUS (default: STATUS).",
    )
    parser.add_argument(
        "--sheet-oe",
        type=str,
        default="SOE",
        help="Nombre de la hoja de salida con SOE en el Excel (default: SOE).",
    )
    parser.add_argument(
        "--tolerancia-ms",
        type=int,
        default=3,
        help="Tolerancia en milisegundos para emparejar eventos Local vs Monarch (default: 3).",
    )

    args = parser.parse_args()
    outdir = _out_pruebas() if args.outdir is None else args.outdir
    os.makedirs(outdir, exist_ok=True)

    _log(f"Usando carpeta de trabajo: {outdir}")

    # --- Rutas esperadas
    path_dir = os.path.join(outdir, "Direcciones.csv")
    path_local = os.path.join(outdir, "SOE_Local.csv")
    path_monarch = os.path.join(outdir, "SOE_Monarch.csv")

    # --- Verificaciones básicas
    for p in (path_dir, path_local, path_monarch):
        if not os.path.isfile(p):
            _log(f"No existe requerido: {p}", "ERROR")
            sys.exit(1)

    if not os.path.isfile(args.checklist):
        _log(f"No existe checklist: {args.checklist}", "ERROR")
        sys.exit(1)

    # --- Cargar Direcciones
    _log("Leyendo Direcciones.csv…")
    df_direcciones = _read_csv_robust(path_dir, encoding="latin-1")
    # Asegurar tipos minimos
    if "IOA" not in df_direcciones.columns:
        _log("Direcciones.csv no contiene la columna 'IOA'.", "ERROR")
        sys.exit(1)

    # --- Cargar SOE Local
    _log("Leyendo SOE_Local.csv…")
    # 'time' puede venir como string con ms; parse_dates intenta convertir
    df_soe_local = _read_csv_robust(path_local, encoding="latin-1")
    # Normalizamos nombres que el script previo genera:
    # Esperamos: ['Fecha','Hora','milli_secs','Tension','Bahia','Equipo','Signal','Event','IOA','event','time']
    if "time" not in df_soe_local.columns:
        _log("SOE_Local.csv no contiene la columna 'time'.", "ERROR")
        sys.exit(1)
    if "event" not in df_soe_local.columns:
        _log("SOE_Local.csv no contiene la columna 'event'.", "ERROR")
        sys.exit(1)
    # Filtrar event != -1 como en el original
    df_soe_local = df_soe_local[df_soe_local["event"] != -1].copy()
    # Sufijo _local
    df_soe_local = df_soe_local.add_suffix("_local")

    # --- Cargar SOE Monarch
    _log("Leyendo SOE_Monarch.csv…")
    df_soe_monarch = _read_csv_robust(path_monarch)
    # Esperamos tener al menos: 'time','IOA','event' y ojalá 'timequality','scanquality'
    need_monarch = {"time", "IOA"}
    missing_m = [c for c in need_monarch if c not in df_soe_monarch.columns]
    if missing_m:
        _log(f"SOE_Monarch.csv sin columnas necesarias: {missing_m}", "ERROR")
        sys.exit(1)

    # Drop duplicates por (time, IOA) como el original
    df_soe_monarch = df_soe_monarch.drop_duplicates(subset=["time", "IOA"]).copy()
    # Sufijo _monarch
    df_soe_monarch = df_soe_monarch.add_suffix("_monarch")

    # --- Cargar Checklist (STATUS)
    _log(f"Leyendo checklist: {args.checklist} (hoja '{args.sheet_status}') …")
    try:
        df_checklist = pd.read_excel(
            args.checklist, sheet_name=args.sheet_status, dtype={"SCADAkey": str}, engine="openpyxl"
        )
    except Exception as e:
        _log(f"No fue posible leer la hoja '{args.sheet_status}': {e}", "ERROR")
        sys.exit(1)

    # Normalizar nombres sin espacios
    df_checklist.columns = df_checklist.columns.str.replace(" ", "", regex=False)

    columnas_checklist = ["IOA", "SCADAkey", "AOR", "type", "Station", "Name", "Prueba"]
    faltantes = [c for c in columnas_checklist if c not in df_checklist.columns]
    if faltantes:
        _log(f"Columnas faltantes en checklist (se continuara con lo disponible): {faltantes}", "WARN")
        # Crear si faltan para evitar KeyError en la salida
        for c in faltantes:
            if c not in df_checklist.columns:
                df_checklist[c] = np.nan

    # Quedarnos con las columnas de interés (las que existan)
    existentes = [c for c in columnas_checklist if c in df_checklist.columns]
    df_checklist = df_checklist[existentes].copy()

    # Filtrar IOA no nulas y a int
    if "IOA" in df_checklist.columns:
        df_checklist = df_checklist[df_checklist["IOA"].notna()].copy()
        df_checklist["IOA"] = df_checklist["IOA"].astype("Int32", errors="ignore")
    else:
        _log("La hoja STATUS no contiene la columna 'IOA'. Se generará salida sin validaciones por IOA.", "WARN")
        df_checklist["IOA"] = pd.Series(dtype="Int32")

    # --- IOA en SE (cruce con Direcciones)
    _log("Verificando IOA del checklist contra Direcciones.csv…")
    df_checklist["IOA_in_SE"] = df_checklist["IOA"].isin(df_direcciones.get("IOA", pd.Series(dtype="Int32")))
    cant_true = df_checklist["IOA_in_SE"].sum()
    total_ioa = len(df_checklist["IOA"])
    _log(f"IOA en checklist: {total_ioa} | Encontradas en Direcciones: {cant_true}")
    _log(f"SOE_Local: {len(df_soe_local)} filas | IOA únicas: {df_soe_local['IOA_local'].nunique()}")
    _log(f"SOE_Monarch: {len(df_soe_monarch)} filas | IOA únicas: {df_soe_monarch['IOA_monarch'].nunique()}")

    if cant_true < total_ioa:
        faltantes_ioa = df_checklist.loc[~df_checklist["IOA_in_SE"], "IOA"]
        _log(f"IOA no encontradas en Direcciones: {list(faltantes_ioa.values)}", "WARN")

    # --- Validaciones SOE
    _log("Preparando emparejamiento de eventos SOE…")
    tol = int(args.tolerancia_ms)

    # Preparar tiempos truncados a décimas (quitamos último dígito)
    df_soe_local["time_local_truncated"] = pd.to_datetime(df_soe_local["time_local"].astype(str).str[:-1])
    df_soe_monarch["time_monarch_truncated"] = pd.to_datetime(df_soe_monarch["time_monarch"].astype(str).str[:-1])

    # Lista de IOA a procesar
    ioas = df_checklist["IOA"].dropna().unique().tolist()
    _log(f"Procesando {len(ioas)} IOA del checklist…")

    resultados = []

    for i, ioa in enumerate(ioas, 1):
        _log(f"  IOA {i}/{len(ioas)}: {ioa}")
        df_l = df_soe_local[df_soe_local["IOA_local"] == ioa][
            ["time_local", "milli_secs_local", "Tension_local", "Bahia_local", "Signal_local", "IOA_local", "event_local", "time_local_truncated"]
        ].copy()
        df_m = df_soe_monarch[df_soe_monarch["IOA_monarch"] == ioa].copy()

        _log(f"    - Eventos Local={len(df_l)} | Monarch={len(df_m)}")

        # 1) Coincidencia exacta de time
        if not df_l.empty and not df_m.empty:
            df_join = df_l.merge(
                df_m,
                left_on="time_local",
                right_on="time_monarch",
                how="inner",
                suffixes=("", ""),
            )
            if not df_join.empty:
                df_join["diff_ms"] = 0
                # Quitar columnas auxiliares
                drop_cols = [c for c in df_join.columns if c.endswith("_truncated") or c.startswith("milli_secs")]
                df_join = df_join.drop(columns=drop_cols, errors="ignore")
                resultados.append(df_join)

        # 2) Coincidencia por truncados +/- tolerancia en ms
        #   haremos un merge por la clave truncada, luego filtramos por |Δms|<=tol
        if not df_l.empty and not df_m.empty:
            aux_l = df_l[["time_local_truncated", "milli_secs_local", "time_local", "Tension_local", "Bahia_local", "Signal_local", "IOA_local", "event_local"]].copy()
            aux_m = df_m[["time_monarch_truncated", "milli_secs_monarch", "time_monarch", "IOA_monarch", "event_monarch", "timequality_monarch", "scanquality_monarch"] if "timequality_monarch" in df_m.columns and "scanquality_monarch" in df_m.columns else ["time_monarch_truncated", "milli_secs_monarch", "time_monarch", "IOA_monarch", "event_monarch"]].copy()

            merged = aux_l.merge(
                aux_m,
                left_on="time_local_truncated",
                right_on="time_monarch_truncated",
                how="inner",
            )
            if not merged.empty:
                merged["diff_ms"] = (merged["milli_secs_local"] - merged["milli_secs_monarch"]).abs()
                merged = merged[merged["diff_ms"] <= tol].copy()
                drop_cols = [c for c in merged.columns if c.endswith("_truncated") or c.startswith("milli_secs")]
                merged = merged.drop(columns=drop_cols, errors="ignore")
                if not merged.empty:
                    resultados.append(merged)

    _log("Combinación completa.")
    if resultados:
        df_soe_combinado = pd.concat(resultados, ignore_index=True)
        _log(f"SOE combinado: {len(df_soe_combinado)} registros.")
        _log(f"IOA combinadas únicas: {df_soe_combinado.get('IOA_monarch', pd.Series(dtype='Int32')).nunique()}")
        try:
            _log(f"Ejemplos de tiempos combinados: {df_soe_combinado[['time_local','time_monarch']].head(3).to_dict(orient='records')}")
        except Exception:
            pass
    else:
        _log("No se encontraron eventos combinados. Se creará DataFrame vacío.", "WARN")
        # Mantener columnas esperadas para que las hojas Excel no queden sin encabezados
        expected_cols = [
            "time_local",
            "milli_secs_local",
            "Tension_local",
            "Bahia_local",
            "Signal_local",
            "IOA_local",
            "event_local",
            "time_monarch",
            "milli_secs_monarch",
            "station_name_monarch",
            "point_name_monarch",
            "state_text_monarch",
            "IOA_monarch",
            "event_monarch",
            "timequality_monarch",
            "scanquality_monarch",
            "valido",
        ]
        df_soe_combinado = pd.DataFrame(columns=expected_cols)

    # --- Validaciones
    _log("Aplicando validaciones…")
    if not df_soe_combinado.empty:
        # Asegurar columnas para evitar KeyError
        for c in ["event_local", "event_monarch", "timequality_monarch", "scanquality_monarch"]:
            if c not in df_soe_combinado.columns:
                df_soe_combinado[c] = np.nan

        val1 = df_soe_combinado["event_local"] == df_soe_combinado["event_monarch"]
        val2 = df_soe_combinado["timequality_monarch"].fillna(0) == 0
        val3 = df_soe_combinado["scanquality_monarch"].fillna(0).isin([0, 16])

        df_soe_combinado["valido"] = np.select(
            [val1 & val2 & val3, ~val1, ~val2, ~val3],
            ["Good", "event", "timequality", "scanquality"],
            default="Other",
        )

        # Formateo de fechas a ms
        for col in ["time_local", "time_monarch"]:
            if col in df_soe_combinado.columns:
                try:
                    dt = pd.to_datetime(df_soe_combinado[col])
                    df_soe_combinado[col] = dt.dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]
                except Exception:
                    pass

    # --- Actualizar checklist con métricas
    _log("Actualizando checklist con resultados SOE…")
    def _count_total(ioa):
        if "IOA_monarch" not in df_soe_combinado.columns:
            return 0
        return int((df_soe_combinado["IOA_monarch"] == ioa).sum())

    def _count_good(ioa):
        if "IOA_monarch" not in df_soe_combinado.columns or "valido" not in df_soe_combinado.columns:
            return 0
        m = (df_soe_combinado["IOA_monarch"] == ioa) & (df_soe_combinado["valido"] == "Good")
        return int(m.sum())

    df_checklist["IOA_SOE"] = df_checklist["IOA"].apply(_count_total)
    df_checklist["IOA_validadas"] = df_checklist["IOA"].apply(_count_good)
    df_checklist.loc[df_checklist["IOA_validadas"] >= 1, "Prueba"] = "Good"
    df_checklist.loc[df_checklist["IOA_validadas"] < 1, "Prueba"] = "No probado"

    # --- Excel de salida
    out_xlsx = os.path.join(outdir, "SOE_completo.xlsx")
    _log(f"Escribiendo Excel: {out_xlsx}")
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        # STATUS actualizado
        df_checklist.to_excel(writer, index=False, sheet_name=args.sheet_status)
        ws_status = writer.sheets[args.sheet_status]
        ws_status.auto_filter.ref = ws_status.dimensions
        ws_status.freeze_panes = "A2"

        # SOE combinado
        df_soe_combinado.to_excel(writer, index=False, float_format="%.0f", sheet_name=args.sheet_oe)
        ws_soe = writer.sheets[args.sheet_oe]
        ws_soe.auto_filter.ref = ws_soe.dimensions
        ws_soe.freeze_panes = "A2"

        # Hoja checklist derivada de SOE
        cols_checklist = [
            "time_monarch",
            "station_name_monarch",
            "point_name_monarch",
            "state_text_monarch",
            "osi_key_monarch",
            "timequality_monarch",
            "scanquality_monarch",
        ]
        df_ck = pd.DataFrame()
        for col in cols_checklist[:-2]:
            df_ck[col] = df_soe_combinado.get(col, "")
        valido_series = df_soe_combinado.get("valido")
        df_ck["timequality_monarch"] = valido_series
        df_ck["scanquality_monarch"] = valido_series
        df_ck.to_excel(writer, index=False, sheet_name="checklist")
        ws_ck = writer.sheets["checklist"]
        ws_ck.auto_filter.ref = ws_ck.dimensions
        ws_ck.freeze_panes = "A2"

    _log("Archivo Excel generado correctamente.", "OK")

    if args.abrir_excel and os.name == "nt":
        _log("Abriendo Excel…")
        subprocess.run(["start", "excel", out_xlsx], shell=True)

    _log("Proceso completado.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        _log(f"Error no controlado: {e}", "ERROR")
        sys.exit(1)
