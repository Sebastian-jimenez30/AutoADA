# scripts/itcosas_v1_soe_local.py
import argparse
import os
import sys
import pandas as pd

# Logger opcional
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
            Logger.write_log().log_all(level, msg, logger_console, None)
        except Exception:
            print(f"[{level.upper()}] {msg}")
    else:
        print(f"[{level.upper()}] {msg}")

Dicc_Events = {
    'Log change to 0': 0,
    'Log change to 1': 1,
    'Alarm on - not ack.': 1,
    'Alarm off - not ack.': 0,
    'Alarm off': 0,
    'User acknowledgement': None,
    'Alarm unavailable': 0,
    'Alarm on - ack.': None,
    'Bit unavailable': None,
    'Bit send 1': 1,
    'Bit send 0': 0
}

def parse_args():
    ap = argparse.ArgumentParser(description="Genera SOE_Local.csv desde Direcciones.csv + EventosDiario.")
    ap.add_argument("--eventos", required=True, help="Ruta al archivo EventosDiario (CSV con ';').")
    ap.add_argument("--direcciones", required=False, default=None,
                    help="Ruta a Direcciones.csv (por defecto out/pruebas/Direcciones.csv).")
    ap.add_argument("--outdir", required=True, help="Carpeta de salida (se guardará SOE_Local.csv).")
    return ap.parse_args()

def main():
    args = parse_args()
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    # Direcciones por defecto en out/pruebas si no llega explícito
    direcciones_path = os.path.abspath(args.direcciones) if args.direcciones \
        else os.path.join(outdir, "Direcciones.csv")
    eventos_path = os.path.abspath(args.eventos)

    # Leer Direcciones.csv (latin-1 / cp1252)
    df_dir = pd.read_csv(direcciones_path, encoding="latin-1")
    # Limpieza y filtros como el script base
    df_dir = df_dir.dropna(subset=['Master'])
    df_dir['Type'] = df_dir['Type'].astype('Int32', errors='ignore')
    df_dir['IOA']  = df_dir['IOA'].astype('Int32', errors='ignore')
    # Solo Type == 1 (status)
    df_dir = df_dir[df_dir['Type'].astype(str) == '1']

    # Leer EventosDiario (delimitador ';')
    df_ev = pd.read_csv(eventos_path, encoding='latin-1', delimiter=';', skipinitialspace=True)
    df_ev = df_ev.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

    # Asignar columnas esperadas
    df_ev.columns = ['Fecha','Hora','Tension','Bahia','Type','Equipo','Signal','Event']

    # Separar milisegundos
    df_ev[['hora_tmp','milli_secs']] = df_ev['Hora'].str.split('.', expand=True)
    df_ev.drop(columns=['Hora'], inplace=True)
    df_ev.rename(columns={'hora_tmp': 'Hora'}, inplace=True)

    df_ev = df_ev[['Fecha','Hora','milli_secs','Tension','Bahia','Equipo','Signal','Event']]

    # Merge por Signal -> Description
    df_merge = pd.merge(
        df_ev,
        df_dir[['Description', 'IOA']],
        left_on='Signal',
        right_on='Description',
        how='left'
    ).drop(columns=['Description'])

    df_merge['IOA'] = df_merge['IOA'].fillna(-1)
    df_merge['event'] = df_merge['Event'].map(Dicc_Events).fillna(-1).astype(int)

    # Construir time con milisegundos
    df_merge['time'] = pd.to_datetime(df_merge['Fecha'] + ' ' + df_merge['Hora'], format='%Y/%m/%d %H:%M:%S')
    df_merge['time'] = df_merge['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df_merge['time'] = df_merge['time'] + '.' + df_merge['milli_secs'].astype(str)

    out_csv = os.path.join(outdir, "SOE_Local.csv")
    df_merge.to_csv(out_csv, index=False, encoding="utf-8")
    log("info", f"Guardado: {out_csv}")
    print(f">> OK: {out_csv}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("error", f"Fallo SOE Local: {e}")
        print(f"[ERROR] {e}")
        sys.exit(1)
