# eliminar_señales_scada.py
# =============================
# Eliminar señales SCADA (STATUS/ANALOG) + export de controles
# =============================
import argparse
import os
import csv
import pandas as pd
import warnings
import sys

try:
    from scripts import _Logger as Logger
except Exception:
    try:
        import _Logger as Logger
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

def _rt() -> str:
    return os.getcwd()

ROOT = _rt()
CARPETA_SALIDA = os.path.join(ROOT, "out", "Delete")
os.makedirs(CARPETA_SALIDA, exist_ok=True)

CARPETA_LOG = os.path.join(ROOT, "log")
os.makedirs(CARPETA_LOG, exist_ok=True)

log_path = os.path.join(CARPETA_LOG, "eliminar_señales.log")
logger, logger_console = Logger.initlog(log_path)

def get_args():
    p = argparse.ArgumentParser(description='Eliminar señales SCADA (STATUS/ANALOG).')
    p.add_argument('archivo_excel', type=str, help='Archivo Excel de entrada')
    p.add_argument('empresa', type=str, help='Nombre de la empresa')
    return p.parse_args()

args = get_args()
ARCHIVO_EXCEL = args.archivo_excel
EMPRESA = args.empresa

# --------- IO / Carga ----------
def cargar_datos_eliminar():
    try:
        try:
            delete = pd.read_excel(ARCHIVO_EXCEL, sheet_name="CAMBIO ELIMINAR", dtype={'SCADA KEY': str})
        except Exception as e:
            Logger.write_log().log_all("warning", f"No se encontró la hoja 'CAMBIO ELIMINAR': {e}", logger_console, logger)
            delete = pd.DataFrame(columns=["SCADA KEY", "DESCRIPCIÓN"])

        # Quitar duplicadas de SCADA KEY
        if not delete.empty and 'SCADA KEY' in delete.columns:
            duplicados = delete[delete['SCADA KEY'].duplicated(keep=False)]
            if not duplicados.empty:
                Logger.write_log().log_all("warning", f"Keys duplicadas en 'CAMBIO ELIMINAR': {duplicados['SCADA KEY'].tolist()}", logger_console, logger)
                delete.drop_duplicates(subset=['SCADA KEY'], keep='first', inplace=True)

        ruta_scada = os.path.join(ROOT, "out", EMPRESA, "SCADA")

        scada_status_df = pd.read_csv(os.path.join(ruta_scada, '10_4.csv'), encoding='ISO-8859-1', low_memory=False, usecols=['Key','ICaddress','Name'])
        scada_analog_df = pd.read_csv(os.path.join(ruta_scada, '10_5.csv'), encoding='ISO-8859-1', low_memory=False, usecols=['Key','ICaddress','Name'])
        controls_df     = pd.read_csv(os.path.join(ruta_scada, '32_20.csv'), encoding='ISO-8859-1', low_memory=False, usecols=['SourceKey','GuidAsString'])

        scada_status_keys = set(scada_status_df['Key'].dropna().astype(str))
        scada_analog_keys = set(scada_analog_df['Key'].dropna().astype(str))
        scada_status_ica  = set(scada_status_df['ICaddress'].dropna().astype(str))
        scada_analog_ica  = set(scada_analog_df['ICaddress'].dropna().astype(str))
        
        # Crear diccionarios key->name para comparaciones posteriores
        scada_status_names = dict(zip(scada_status_df['Key'].astype(str), scada_status_df['Name']))
        scada_analog_names = dict(zip(scada_analog_df['Key'].astype(str), scada_analog_df['Name']))

        Logger.write_log().log_all("info", "Archivos cargados correctamente.", logger_console, logger)
        return delete, scada_status_keys, scada_analog_keys, controls_df, scada_status_ica, scada_analog_ica, scada_status_names, scada_analog_names
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al cargar archivos: {e}", logger_console, logger)
        return None, None, None, None, None, None, None, None

# --------- Lógica ---------
def asignar_status_analog(key, scada_status, scada_analog):
    key = str(key).strip().upper()
    if key in scada_status:
        return 'STATUS'
    elif key in scada_analog:
        return 'ANALOG'
    return key

def verificar_icaddress(keys, scada_status_ica, scada_analog_ica):
    log = Logger.write_log()
    for key in keys:
        if key in scada_status_ica:
            log.log_all("warning", f"La key: {key} está en ICaddress de scada_Status", logger_console, logger)
        elif key in scada_analog_ica:
            log.log_all("warning", f"La key: {key} está en ICaddress de scada_Analog", logger_console, logger)
#----Verificación de nombres diferentes entre excel y scada-----          
def verificar_errores_nombres(delete_df, scada_status_names, scada_analog_names):
    log = Logger.write_log()
    errores = []
    for _, row in delete_df.iterrows():
        key = str(row['SCADA KEY']).strip().upper()
        nombre_delete = str(row['DESCRIPCIÓN']).strip() if pd.notna(row['DESCRIPCIÓN']) else ""
        
        # Verificar en STATUS
        if key in scada_status_names:
            nombre_scada = str(scada_status_names[key]).strip()
            if nombre_delete != nombre_scada:
                log.log_all("warning", 
                            f"Diferencias en STATUS - Key: {key}\n"
                            f"  Nombre en Excel: '{nombre_delete}'\n"
                            f"  Nombre en SCADA : '{nombre_scada}'", 
                            logger_console, logger)
                errores.append((key, "STATUS", nombre_delete, nombre_scada))
                
        # Verificar en ANALOG
        elif key in scada_analog_names:
            nombre_scada = str(scada_analog_names[key]).strip()
            if nombre_delete != nombre_scada:
                log.log_all("warning", 
                            f"Diferencias en ANALOG - Key: {key}\n"
                            f"  Nombre en Excel: '{nombre_delete}'\n"
                            f"  Nombre en SCADA : '{nombre_scada}'", 
                            logger_console, logger)
                errores.append((key, "ANALOG", nombre_delete, nombre_scada))

    return len(errores) > 0

def preparar_dataframe_delete(df, tipo, columna_extra):
    if df.empty:
        Logger.write_log().log_all("info", f"DataFrame vacío para {tipo}.", logger_console, logger)
        return None

    df = df.copy()
    df.insert(0, columna_extra, [None] * len(df))
    df.insert(1, tipo, [None] * len(df))
    df.insert(2, 'Delete', ['1'] * len(df))
    df.rename(columns={'SCADA KEY': 'Key', 'DESCRIPCIÓN': 'Name'}, inplace=True)
    df = df[['5' if tipo == 'ANALOG' else '4', tipo, 'Delete', 'Key', 'Name']]
    df[['Key', 'Name']] = df[['Key', 'Name']].map(lambda x: f'"{x}"')
    Logger.write_log().log_all("info", f"DF preparado: {tipo}", logger_console, logger)
    return df

def guardar_delete_csv(df_status, df_analog, path):
    if (df_status is None or df_status.empty) and (df_analog is None or df_analog.empty):
        Logger.write_log().log_all("warning", "Ambos DataFrames vacíos, no se guarda archivo de eliminación.", logger_console, logger)
        return
    with open(path, 'w', newline='') as f:
        f.write("10,SCADA.DB\n")
        if df_status is not None and not df_status.empty:
            df_status.to_csv(f, index=False, quoting=csv.QUOTE_NONE)
            f.write("0\n")
        if df_analog is not None and not df_analog.empty:
            if df_status is not None and not df_status.empty:
                f.write("*\n")
            df_analog.to_csv(f, index=False, quoting=csv.QUOTE_NONE)
            f.write("0\n")
        f.write("0")
    Logger.write_log().log_all("info", f"Archivo de eliminación guardado: {path}", logger_console, logger)


def exportar_controls_csv(keys, controls_df, output_path):
    keys_set = set(str(k).strip().upper() for k in keys)
    controls_df = controls_df.copy()
    controls_df['SourceKey'] = controls_df['SourceKey'].astype(str).str.strip().str.upper()
    df_filtrado = controls_df[controls_df['SourceKey'].isin(keys_set)][['SourceKey', 'GuidAsString']]
    if df_filtrado.empty:
        Logger.write_log().log_all("warning", "No hay controles para exportar.", logger_console, logger)
        return
    df_filtrado.insert(0, 'Delete', '1')
    df_filtrado.insert(0, 'RTU_CONTROL', None)
    df_filtrado.insert(0, '20', None)
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        f.write("32,FEP.DB\n")
        f.write("20,RTU_CONTROL,Delete,SourceKey,GuidAsString\n")
        df_filtrado.to_csv(f, index=False, header=False, quoting=csv.QUOTE_NONE)
        f.write("0\n0")
    Logger.write_log().log_all("info", f"Guardado: {output_path}", logger_console, logger)

def limpiar_directorio(path):
    if not os.path.exists(path):
        os.makedirs(path)
        Logger.write_log().log_all("info", f"Directorio {path} creado.", logger_console, logger)

# --------- Main pipeline ---------
def main():
    delete, scada_status, scada_analog, controls, scada_status_ica, scada_analog_ica, scada_status_names, scada_analog_names = cargar_datos_eliminar()
    if any(x is None for x in [delete, scada_status, scada_analog, controls]):
        print("No se pudieron cargar los datos necesarios. Proceso abortado.")
        return

    try:
        delete['Tipo'] = delete['SCADA KEY'].apply(lambda k: asignar_status_analog(k, scada_status, scada_analog))
        Logger.write_log().log_all("info", f"STATUS: {(delete['Tipo'] == 'STATUS').sum()} | ANALOG: {(delete['Tipo'] == 'ANALOG').sum()}", logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al asignar tipos: {e}", logger_console, logger)
        print(f"Error al asignar tipos: {e}")
        return

    limpiar_directorio(CARPETA_SALIDA)

# Verificar diferencias en los nombres de las señales
    Logger.write_log().log_all("info", "Verificando diferencias en nombres de señales...", logger_console, logger)
    hay_diferencias = verificar_errores_nombres(delete, scada_status_names, scada_analog_names)
    if hay_diferencias:
        Logger.write_log().log_all("error", "Se encontraron diferencias en los nombres de señales. Proceso abortado.", logger_console, logger)
        sys.exit(1) 
    
    # Advertencias por ICaddress
    keys_ica = delete['SCADA KEY'].dropna().astype(str).tolist()
    verificar_icaddress(keys_ica, scada_status_ica, scada_analog_ica)
    
    # Guardar archivos de eliminación
    try:
        df_status = preparar_dataframe_delete(delete[delete['Tipo'] == 'STATUS'], 'STATUS', '4')
        df_analog = preparar_dataframe_delete(delete[delete['Tipo'] == 'ANALOG'], 'ANALOG', '5')
        guardar_delete_csv(df_status, df_analog, os.path.join(CARPETA_SALIDA, 'Delete_scada.csv'))
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al guardar Delete_scada.csv: {e}", logger_console, logger)
        print(f"Error al guardar Delete_scada.csv: {e}")

    # Export de controles
    try:
        keys_para_controles = delete['SCADA KEY'].dropna().astype(str).tolist()
        exportar_controls_csv(keys_para_controles, controls, os.path.join(CARPETA_SALIDA, 'Delete_controls.csv'))
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al guardar Delete_controls.csv: {e}", logger_console, logger)
        print(f"Error al guardar Delete_controls.csv: {e}")

if __name__ == "__main__":
    try:
        main()
        Logger.write_log().log_all("info", "Proceso de eliminación finalizado correctamente.", logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all("error", f"Error general: {e}", logger_console, logger)
        sys.exit(1)
