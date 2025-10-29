# =============================
# Script para eliminar y cambiar nombre de señales SCADA
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

log_path = os.path.join(CARPETA_LOG, "eliminar_cambiar_name.log")
logger, logger_console = Logger.initlog(log_path)

def get_args():
    parser = argparse.ArgumentParser(description='Script para convertir bases de datos SCADA.')
    parser.add_argument('archivo_excel', type=str, help='Archivo Excel de entrada')
    parser.add_argument('empresa', type=str, help='Nombre de la empresa')
    return parser.parse_args()

args = get_args()
ARCHIVO_EXCEL = args.archivo_excel
empresa = args.empresa

# =============================
# Función para cargar datos de archivos
# =============================
def cargar_datos():
    """
    Carga las hojas necesarias del archivo Excel y los archivos SCADA requeridos.
    Devuelve los DataFrames y conjuntos necesarios para el procesamiento.
    """
    try:
        # Cargar hojas del Excel, tolerando ausencia de alguna hoja
        try:
            delete = pd.read_excel(ARCHIVO_EXCEL, sheet_name="CAMBIO ELIMINAR", dtype={'SCADA KEY': str})
        except Exception as e:
            Logger.write_log().log_all("warning", f"No se encontró la hoja 'CAMBIO ELIMINAR': {e}", logger_console, logger)
            delete = pd.DataFrame(columns=["SCADA KEY", "DESCRIPCIÓN"])

        try:
            change_key = pd.read_excel(ARCHIVO_EXCEL, sheet_name="CAMBIO SCADA", dtype={'SCADA KEY': str})
        except Exception as e:
            Logger.write_log().log_all("warning", f"No se encontró la hoja 'CAMBIO SCADA': {e}", logger_console, logger)
            change_key = pd.DataFrame(columns=["SCADA KEY", "DESCRIPCIÓN", "DESCRIPCIÓN NUEVA"])

        # Verificar y eliminar keys duplicadas en ambas hojas
        for df, nombre in [(delete, 'CAMBIO ELIMINAR'), (change_key, 'CAMBIO SCADA')]:
            if not df.empty and 'SCADA KEY' in df.columns:
                duplicados = df[df['SCADA KEY'].duplicated(keep=False)]
                if not duplicados.empty:
                    Logger.write_log().log_all("warning", f"Keys duplicadas en hoja '{nombre}': {duplicados['SCADA KEY'].tolist()}", logger_console, logger)
                    # Eliminar duplicados, dejando solo la primera aparición
                    df.drop_duplicates(subset=['SCADA KEY'], keep='first', inplace=True)

        # Definir ruta de archivos SCADA (desde CWD)
        ruta_scada = os.path.join(ROOT, "out", empresa, "SCADA")

        # Cargar archivos SCADA con manejo robusto de tipos
        scada_status = pd.read_csv(os.path.join(ruta_scada, '10_4.csv'), encoding='ISO-8859-1', low_memory=False, usecols=['Key','ICaddress'])
        scada_analog = pd.read_csv(os.path.join(ruta_scada, '10_5.csv'), encoding='ISO-8859-1', low_memory=False, usecols=['Key','ICaddress'])
        controls = pd.read_csv(os.path.join(ruta_scada, '32_20.csv'), encoding='ISO-8859-1', low_memory=False, usecols=['SourceKey','GuidAsString'])

        # Convertir a conjuntos para búsqueda eficiente
        scada_status_ica = set(scada_status['ICaddress'].dropna().astype(str))
        scada_analog_ica = set(scada_analog['ICaddress'].dropna().astype(str))
        scada_status = set(scada_status['Key'].dropna().astype(str))
        scada_analog = set(scada_analog['Key'].dropna().astype(str))

        Logger.write_log().log_all("info", "Archivos cargados correctamente.", logger_console, logger)
        return delete, change_key, scada_status, scada_analog, controls, scada_status_ica, scada_analog_ica
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al cargar los archivos: {e}", logger_console, logger)
        return None, None, None, None, None, None, None

# =============================
# Asignación de tipo de señal
# =============================
def asignar_status_analog(key, scada_status, scada_analog):
    key = str(key).strip().upper()
    if key in scada_status:
        return 'STATUS'
    elif key in scada_analog:
        return 'ANALOG'
    return key

# =============================
# Asignación de keys que se encuentran en icaddress en scada
# =============================
def verificar_icaddress(keys, scada_status_ica, scada_analog_ica, logger_console, logger):
    logger_instance = Logger.write_log()
    for key in keys:
        if key in scada_status_ica:
            logger_instance.log_all("warning", f"La key: {key} está en el campo ICaddress de scada_Status", logger_console, logger)
        elif key in scada_analog_ica:
            logger_instance.log_all("warning", f"La key: {key} está en el campo ICaddress de scada_Analog", logger_console, logger)

# =============================
# Exportar controles a CSV con formato especial
# =============================
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

# =============================
# Preparar DataFrame para eliminación
# =============================
def preparar_dataframe_delete(df, tipo, columna_extra):
    if df.empty:
        Logger.write_log().log_all("info", f"DataFrame vacío para tipo {tipo}.", logger_console, logger)
        return None

    df = df.copy()
    df.insert(0, columna_extra, [None] * len(df))
    df.insert(1, tipo, [None] * len(df))
    df.insert(2, 'Delete', ['1'] * len(df))
    df.rename(columns={'SCADA KEY': 'Key', 'DESCRIPCIÓN': 'Name'}, inplace=True)
    df = df[['5' if tipo == 'ANALOG' else '4', tipo, 'Delete', 'Key', 'Name']]
    # (Se mantiene la misma lógica original)
    df[['Key', 'Name']] = df[['Key', 'Name']].map(lambda x: f'"{x}"')

    Logger.write_log().log_all("info", f"DataFrame preparado: {tipo}", logger_console, logger)
    return df

# =============================
# Preparar DataFrame para cambio de clave
# =============================
def preparar_dataframe_change_key(df):
    if df.empty:
        Logger.write_log().log_all("warning", "DataFrame CAMBIO SCADA vacío. No se creará archivo.", logger_console, logger)
        return None

    df = df.copy()
    df['New Tipo'] = df['Tipo'].map({'ANALOG': 5, 'STATUS': 4}).fillna(0).astype(int)
    df['New Desc.'] = df['DESCRIPCIÓN NUEVA'].apply(lambda x: f'"{x}"')

    df = pd.concat([
        pd.Series(['dbset-k'] * len(df), name='dbset'),
        pd.Series(['10'] * len(df), name='db'),
        df['New Tipo'],
        pd.Series(['4'] * len(df), name='C.name'),
        df.pop('SCADA KEY'),
        pd.Series(['0'] * len(df), name='0'),
        pd.Series(['='] * len(df), name='simbolo'),
        df['New Desc.']
    ], axis=1)
    return df

# =============================
# Guardar DataFrames en CSV con formato especial
# =============================
def guardar_csv(df1, df2, path):
    if (df1 is None or df1.empty) and (df2 is None or df2.empty):
        Logger.write_log().log_all("warning", "Ambos DataFrames están vacíos. No se guardará el archivo.", logger_console, logger)
        return

    with open(path, 'w', newline='') as f:
        f.write("10,SCADA.DB\n")
        if df1 is not None and not df1.empty:
            df1.to_csv(f, index=False, quoting=csv.QUOTE_NONE)
            f.write("0\n")
            if df2 is not None and not df2.empty:
                f.write("*\n")
        if df2 is not None and not df2.empty:
            df2.to_csv(f, index=False, quoting=csv.QUOTE_NONE)
            f.write("0\n0")

    Logger.write_log().log_all("info", f"Guardado: {path}", logger_console, logger)

# =============================
# Guardar DataFrame como TXT plano
# =============================
def guardar_txt(df, path):
    if df is None:
        return
    with open(path, 'w', encoding='utf-8') as f:
        for row in df.itertuples(index=False, name=None):
            f.write(' '.join(str(x) for x in row) + '\n')
    Logger.write_log().log_all("info", f"Guardado: {path}", logger_console, logger)

# =============================
# Crear directorio de salida si no existe
# =============================
def limpiar_directorio(path):
    if not os.path.exists(path):
        os.makedirs(path)
        Logger.write_log().log_all("info", f"Directorio {path} creado.", logger_console, logger)

# =============================
# Pipeline principal de procesamiento
# =============================
def procesar_datos():
    delete, change_key, scada_status, scada_analog, controls, scada_status_ica, scada_analog_ica = cargar_datos()
    if any(x is None for x in [delete, change_key, scada_status, scada_analog, controls]):
        Logger.write_log().log_all("error", "No se pudieron cargar los datos necesarios. Proceso abortado.", logger_console, logger)
        print("No se pudieron cargar los datos necesarios. Proceso abortado.")
        return

    try:
        delete['Tipo'] = delete['SCADA KEY'].apply(lambda k: asignar_status_analog(k, scada_status, scada_analog))
        change_key['Tipo'] = change_key['SCADA KEY'].apply(lambda k: asignar_status_analog(k, scada_status, scada_analog))
        Logger.write_log().log_all("info", f"Claves STATUS: {(delete['Tipo'] == 'STATUS').sum()}", logger_console, logger)
        Logger.write_log().log_all("info", f"Claves ANALOG: {(delete['Tipo'] == 'ANALOG').sum()}", logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al asignar tipos: {e}", logger_console, logger)
        print(f"Error al asignar tipos: {e}")
        return

    limpiar_directorio(CARPETA_SALIDA)

    keys_ica = delete['SCADA KEY'].tolist()
    verificar_icaddress(keys_ica, scada_status_ica, scada_analog_ica, logger_console, logger)

    try:
        guardar_csv(
            preparar_dataframe_delete(delete[delete['Tipo'] == 'STATUS'], 'STATUS', '4'),
            preparar_dataframe_delete(delete[delete['Tipo'] == 'ANALOG'], 'ANALOG', '5'),
            os.path.join(CARPETA_SALIDA, 'Delete_scada.csv')
        )
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al guardar Delete_scada.csv: {e}", logger_console, logger)
        print(f"Error al guardar Delete_scada.csv: {e}")

    try:
        guardar_txt(
            preparar_dataframe_change_key(change_key),
            os.path.join(CARPETA_SALIDA, 'change_key.csv')
        )
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al guardar change_key.csv: {e}", logger_console, logger)
        print(f"Error al guardar change_key.csv: {e}")

    try:
        keys_para_controles = delete['SCADA KEY'].tolist()
        exportar_controls_csv(
            keys_para_controles, controls,
            os.path.join(CARPETA_SALIDA, 'Delete_controls.csv')
        )
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al guardar Delete_controls.csv: {e}", logger_console, logger)
        print(f"Error al guardar Delete_controls.csv: {e}")

if __name__ == "__main__":
    try:
        procesar_datos()
        Logger.write_log().log_all("info", "Proceso finalizado correctamente.", logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all("error", f"Error general: {e}", logger_console, logger)
        sys.exit(1)
