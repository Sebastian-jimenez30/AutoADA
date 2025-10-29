# scripts/itcosas_v1_ioa.py
import argparse
import os
import sys
import pandas as pd

# --- Logger opcional si ya existe en tu repo ---
try:
    from scripts import _Logger as Logger
except Exception:
    Logger = None

def log(level, msg):
    if Logger:
        logger_console, logger = None, None
        try:
            log_path = os.path.join(os.getcwd(), "log", "pruebas.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            _, _ = Logger.initlog(log_path)
        except Exception:
            pass
        try:
            Logger.write_log().log_all(level, msg, logger_console, logger)
        except Exception:
            print(f"[{level.upper()}] {msg}")
    else:
        print(f"[{level.upper()}] {msg}")

def parse_args():
    ap = argparse.ArgumentParser(description="Genera Direcciones.csv (IOA) desde tmwgateway + varexp.")
    ap.add_argument("--tmwgateway", required=True, help="Ruta al archivo tmwgateway (CSV exportado).")
    ap.add_argument("--varexp", required=True, help="Ruta al archivo varexp (DAT/CSV).")
    ap.add_argument("--outdir", required=True, help="Carpeta de salida (se guardará Direcciones.csv).")
    return ap.parse_args()

def main():
    args = parse_args()
    tmw_path = os.path.abspath(args.tmwgateway)
    var_path = os.path.abspath(args.varexp)
    outdir   = os.path.abspath(args.outdir)

    os.makedirs(outdir, exist_ok=True)

    # ---- tmwgateway ----
    # Columnas por posición (como en tu script original)
    columnas_gtway = ['0','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20']
    df_gtway = pd.read_csv(tmw_path, header=None, names=columnas_gtway, encoding="latin-1", low_memory=False)
    df_gtway = df_gtway[['0', '9', '12', '13']]
    df_gtway.columns = ['OPC_ItemId', 'Master', 'Type', 'IOA']

    # ---- varexp ----
    # Usa índices 15,136,137,138,139,152 como en el original (csv/“dat” separado por coma, header=1)
    columnas_varexp = [15, 136, 137, 138, 139, 152]
    df_dat = pd.read_csv(var_path, sep=',', header=1, encoding='cp1252',
                         usecols=columnas_varexp, skipinitialspace=True, low_memory=False)

    # Limpieza básica
    df_dat = df_dat.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    # En ambos, asegurar texto en la llave
    df_gtway['OPC_ItemId'] = df_gtway['OPC_ItemId'].astype(str)
    df_dat.rename(columns={15: 'OPC_ItemId'}, inplace=True, errors='ignore')
    if 'OPC_ItemId' not in df_dat.columns:
        # Fallback: si el archivo trae encabezados “raros”, intenta ubicar la que contenga “OPC”
        cand = [c for c in df_dat.columns if 'opc' in str(c).lower()]
        if cand:
            df_dat.rename(columns={cand[0]: 'OPC_ItemId'}, inplace=True)

    # Tipos
    df_gtway['Type'] = pd.to_numeric(df_gtway['Type'], errors='ignore')
    df_gtway['IOA']  = pd.to_numeric(df_gtway['IOA'],  errors='ignore')
    # Dropear OPC vacíos
    df_gtway = df_gtway.dropna(subset=['OPC_ItemId'])
    df_dat   = df_dat.dropna(subset=['OPC_ItemId'])

    # Merge
    df_combinado = pd.merge(df_gtway, df_dat, on='OPC_ItemId', how='inner')
    # Normalización de caracteres (¤ → ñ)
    df_combinado = df_combinado.replace('¤', 'ñ', regex=True)

    # Salida
    out_csv = os.path.join(outdir, "Direcciones.csv")
    df_combinado.to_csv(out_csv, index=False, encoding="cp1252")
    log("info", f"Guardado: {out_csv}")
    print(f">> OK: {out_csv}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("error", f"Fallo IOA: {e}")
        print(f"[ERROR] {e}")
        sys.exit(1)
