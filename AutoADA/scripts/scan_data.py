import argparse
import os
import pandas as pd
import csv
import numpy as np
import sys
import traceback
import warnings
import unicodedata

# Suprimir warnings de pandas y openpyxl
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

try:
    # cuando se ejecuta como paquete: python -m scripts.buscar_key
    from scripts import _Logger as Logger
except Exception:
    try:
        # cuando se ejecuta como script “plano”
        import _Logger as Logger
    except Exception:
        # último recurso: agregar la carpeta "scripts" al sys.path
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger

def _rt() -> str:
    return os.getcwd()

_rt_dir = _rt()
_log_dir = os.path.join(_rt_dir, 'log')
os.makedirs(_log_dir, exist_ok=True)
log_path = os.path.join(_log_dir, 'Scada_load.log')
logger, logger_console = Logger.initlog(log_path, append=False)  # Sobrescribe el log al iniciar


def _scada_path(root: str, empresa: str, dominio: str | None = None) -> str:
    """
    Construye ruta a la carpeta SCADA segun dominio.
    Ej: dominio='qa' -> out/<empresa>/qaSCADA, sin dominio -> out/<empresa>/SCADA.
    """
    suffix = f"{dominio}SCADA" if dominio else "SCADA"
    return os.path.join(root, "out", empresa, suffix)

def get_args():
    parser = argparse.ArgumentParser(description='Script para convertir bases de datos SCADA.')
    parser.add_argument('archivo_excel', type=str, help='Archivo Excel de entrada')
    parser.add_argument('empresa', type=str, help='Nombre de la empresa')
    parser.add_argument('--dominio', type=str, default=None, help='Dominio (ej: CC, QA) para segmentar rutas SCADA')
    return parser.parse_args()

# =============================
# Funciones
# =============================
def normalizar_texto_sin_tildes(texto):
    """
    Remueve tildes y acentos de un texto, manteniendo otros caracteres especiales.
    """
    if pd.isna(texto) or texto == '':
        return texto
    
    # Convertir a string si no lo es
    texto_str = str(texto)
    
    # Normalizar usando NFD (descomposición) para separar caracteres base de acentos
    texto_normalizado = unicodedata.normalize('NFD', texto_str)
    
    # Filtrar solo caracteres que no sean marcas diacríticas (tildes, acentos)
    texto_sin_tildes = ''.join(char for char in texto_normalizado 
                              if unicodedata.category(char) != 'Mn')
    
    return texto_sin_tildes

def normalizar_dataframe(df):
    """
    Normaliza todas las columnas de texto de un DataFrame removiendo tildes.
    """
    if df.empty:
        return df
        
    df_normalizado = df.copy()
    
    # Aplicar normalización solo a columnas válidas de tipo object (string)
    for columna in df_normalizado.columns:
        try:
            # Verificar que la columna sea válida (no NaN, no espacios vacíos)
            if pd.isna(columna) or str(columna).strip() == '' or str(columna).lower() == 'nan':
                continue
                
            # Verificar que la columna tenga tipo object
            if df_normalizado[columna].dtype == 'object':
                df_normalizado[columna] = df_normalizado[columna].apply(normalizar_texto_sin_tildes)
        except Exception as e:
            # Si hay error con una columna específica, continuar con las demás
            continue
    
    return df_normalizado

def leer_hojas_excel(ruta_archivo):
    Logger.write_log().log_all('info', f"Leyendo archivo Excel: {ruta_archivo}", logger_console, logger)
    try:
        # Leer todas las hojas sin asumir estructura de encabezado
        dfs = pd.read_excel(ruta_archivo, sheet_name=None, header=None)
        Logger.write_log().log_all('info', f"Archivo Excel leído correctamente: {ruta_archivo}", logger_console, logger)

        dfs_procesados = {}
        for nombre_hoja, df in dfs.items():
            # Configurar columnas de forma segura, manejar casos con filas insuficientes
            if len(df) >= 2:
                df.columns = df.iloc[1]
                df = df.iloc[2:]  # Eliminar filas de encabezado

            # Limpiar y reiniciar dataframe
            df = df.dropna(how='all').reset_index(drop=True)
            
            # Normalizar nombres de columnas removiendo tildes y limpiando nombres inválidos
            if not df.empty:
                new_columns = []
                for i, col in enumerate(df.columns):
                    if pd.isna(col) or str(col).strip() == '' or str(col).lower() == 'nan':
                        new_columns.append(f'Column_{i}')  # Nombre genérico para columnas inválidas
                    else:
                        new_columns.append(normalizar_texto_sin_tildes(str(col)))
                df.columns = new_columns
                
                # Normalizar contenido removiendo tildes
                df = normalizar_dataframe(df)
            
            dfs_procesados[nombre_hoja] = df

        return dfs_procesados
    except Exception as e:
        Logger.write_log().log_all('error', f"Error al leer archivo Excel: {e}", logger_console, logger)
        print(f"Error al leer archivo Excel: {e}")
        return {}

def procesar_dataframes(dfs):
    Logger.write_log().log_all('info', "Procesando DataFrames STATUS y ANALOG", logger_console, logger)
    try:
        status = dfs.get('STATUS', pd.DataFrame()).dropna(subset=['Name']).copy()
        analog = dfs.get('ANALOG', pd.DataFrame()).dropna(subset=['Name']).copy()
        # Selección y combinación de columnas
        columnas_mantener = ['RTU', 'Monitoring Type', 'Name', 'Monitoring Address', 'Type', 'Station','Import ICCP Name']
        status['S-A'] = 'STATUS'
        analog['S-A'] = 'ANALOG'
        df_combinado = pd.concat([status[columnas_mantener + ['S-A']], analog[columnas_mantener + ['S-A']]], ignore_index=True)
        df_combinado = df_combinado.loc[:, ~df_combinado.columns.duplicated()]
        Logger.write_log().log_all('info', "DataFrames combinados correctamente", logger_console, logger)
        return df_combinado
    except Exception as e:
        Logger.write_log().log_all('error', f"Error procesando DataFrames: {e}", logger_console, logger)
        print(f"Error procesando DataFrames: {e}")
        return pd.DataFrame()

def extraer_rtu(df):
    # Extracción vectorizada de RTU (si existe la columna)
    if 'RTU' in df.columns and df['RTU'].notna().any():
        df['pRTU'] = df['RTU'].str.split(':').str[0]
        # Verificar unicidad de RTU
        cantidad_rtu_unico = df['pRTU'].nunique()
        Logger.write_log().log_all('info', f"Cantidad de valores de RTU únicos: {cantidad_rtu_unico}", logger_console, logger)
    else:
        # Si no hay RTU, crear columna vacía para evitar errores
        df['pRTU'] = None
        Logger.write_log().log_all('info', "No hay valores de RTU (señales manuales/cálculo)", logger_console, logger)
    return df

def mapear_tipos_monitoreo(df):
    tipos = {'SP': "01", 'DP': "02", 'MV': "03", 'ST': "04"}
    opciones = {'SP': "1", 'DP': "2", 'MV': "3", 'ST': "4"}
    df['Typex'] = df['Monitoring Type'].map(tipos)
    df['ProtocolType'] = df['Monitoring Type'].map(opciones)
    return df

def convertir_numero(num):
    if num <= 999:
        return str(num).zfill(3)
    elif num <= 3599:
        letra = chr((num - 1000) // 100 + 65)
        resto = num % 100
        return letra + str(resto).zfill(2)
    else:
        raise ValueError("El número no puede exceder 3599")

def crear_claves_scada(df, columna_tipo, columna_rtu, inicio):
    if inicio == 0:
        inicio = 1
    df = df.copy()
    df['PointAddress'] = np.arange(inicio, inicio + len(df))
    # Generación vectorizada de claves
    df['Key'] = (
        df[columna_tipo].astype(str) +
        df[columna_rtu].astype(str).str.zfill(3) +
        df['PointAddress'].apply(convertir_numero)
    )
    return df

def desconvertir_lista(lista):
    resultados = []
    for cadena in lista:
        if cadena.isdigit() and len(cadena) == 3:
            resultados.append(int(cadena))
        elif len(cadena) == 3 and cadena[0].isalpha() and cadena[1:].isdigit():
            letra = cadena[0]
            resto = int(cadena[1:])
            num = (ord(letra) - 65) * 100 + 1000 + resto
            resultados.append(num)
        else:
            raise ValueError(f"Formato de cadena no válido: {cadena}")
    return resultados

def buscar_valores(df, data, valor_a_verificar, rtu):
    # Determinar el valor de RTU (desde df o argumento)
    valor_rtu = rtu if df.empty else float(df['pRTU'].iloc[0])

    # Buscar fila correspondiente al valor RTU en 'data'
    result_row = data[data['record'] == valor_rtu]

    # Filtrar columnas tipo 'PointType[...]'
    columnas_punto_tipo = [col for col in result_row.columns if col.startswith('PointType')]

    # Buscar coincidencia directa
    for nombre_columna in columnas_punto_tipo:
        indices = result_row[result_row[nombre_columna] == valor_a_verificar].index
        if not indices.empty:
            break
    else:
        # Si no se encuentra el valor, buscar PointType[...] == 0
        for nombre_columna in columnas_punto_tipo:
            indices = result_row[result_row[nombre_columna] == 0].index
            if not indices.empty:
                warning_msg = f'RTU {int(valor_rtu)}: No existe PointType con valor {valor_a_verificar}, se utilizará {nombre_columna}. Recuerde configurar Start en 1'
                Logger.write_log().log_all('warning', warning_msg, logger_console, logger)
                break

    # Si aún no se encuentra nada, retornar por defecto
    if indices.empty:
        return 0, 0

    # Tomar el primer índice encontrado
    indice = indices[0]

    # Extraer índice entre corchetes, si aplica
    if nombre_columna == 'PointType':
        indice_columna = ''
    else:
        indice_columna = nombre_columna[nombre_columna.find("[") + 1: nombre_columna.find("]")]

    columna_inicio = f"Start{f'[{indice_columna}]' if indice_columna else ''}"
    columna_conteo = f"Count{f'[{indice_columna}]' if indice_columna else ''}"

    if df.empty:
        valor_conteo = int(data.at[indice, columna_conteo])
        return 0, (columna_conteo, valor_conteo)
    else:
        valor_inicio = int(data.at[indice, columna_inicio])
        valor_conteo = int(data.at[indice, columna_conteo])
        nuevo_count = (columna_conteo, valor_conteo + len(df))
        return valor_inicio + valor_conteo, nuevo_count

def asignar_claves_41(datafrem, scada):
    # Asegurarse de que la columna 'Key' exista y sea tipo objeto
    datafrem = datafrem.copy()  # Crear copia explícita para evitar SettingWithCopyWarning
    if 'Key' not in datafrem.columns:
        datafrem['Key'] = pd.NA
    datafrem['Key'] = datafrem['Key'].astype('object')
    new_keys_list = []
    for index, row in datafrem.iterrows():
        rtu_num = row['pRTU']
        rtu_pattern = f"41{int(rtu_num):03d}"
        # Filtrar claves que comienzan con el patrón
        filtered_keys = scada.loc[scada['Key'].astype(str).str.startswith(rtu_pattern), 'Key']
        if not filtered_keys.empty:
            suffixes_from_scada = filtered_keys.astype(str).str[-3:].tolist()
        else:
            suffixes_from_scada = []

        suffixes_from_new = [str(key)[-3:] for key in new_keys_list if str(key).startswith(rtu_pattern)]
        all_suffixes = sorted(set(suffixes_from_scada + suffixes_from_new))
        existing_keys = desconvertir_lista(all_suffixes)

        if existing_keys:
            all_possible = set(range(int(existing_keys[0]), int(existing_keys[-1]) + 1))
            missing_keys = sorted(all_possible - set(existing_keys))
        else:
            missing_keys = []

        if missing_keys:
            new_suffix = convertir_numero(missing_keys[0])
        else:
            new_suffix = convertir_numero(int(max(existing_keys)) + 1) if existing_keys else "001"

        new_key = rtu_pattern + new_suffix
        new_keys_list.append(new_key)
        datafrem.at[index, 'Key'] = new_key
    return datafrem

def procesar_nuevos_count(df):
    resultado = pd.DataFrame()
    # Copiar la columna '#Record' si existe, o 'Record' si esa es la que existe
    if '#Record' in df.columns:
        resultado['#Record'] = df['#Record']
    elif 'Record' in df.columns:
        resultado['#Record'] = df['Record']
    else:
        raise ValueError("El DataFrame debe contener una columna 'Record' o '#Record'")

    # Generar todas las columnas Count del 0 al 31 con valores 0
    for i in range(32):
        nombre_columna = f'Count;{i}'
        resultado[nombre_columna] = 0

    # Verificar si existe una columna "Count" sin índice (tratarla como Count[0])
    if 'Count' in df.columns:
        resultado['Count;0'] = df['Count']

    # Actualizar con los valores reales del DataFrame de entrada
    for columna in df.columns:
        if columna.startswith('Count[') and columna.endswith(']'):
            # Extraer el número entre corchetes
            num = int(columna.replace('Count[', '').replace(']', ''))
            if 0 <= num <= 31:  # Asegurarse de que está en el rango válido
                nombre_columna_salida = f'Count;{num}'
                resultado[nombre_columna_salida] = df[columna]
    return resultado

def merge_and_save_excel(data_dict, key_df):
    # Obtener DataFrames y procesar en un solo bucle
    resultados = {}
    for tipo in ['STATUS', 'ANALOG']:
        df = data_dict.get(tipo, pd.DataFrame())
        
        if df.empty:
            Logger.write_log().log_all('info', f"Hoja {tipo} vacía o no encontrada", logger_console, logger)
            continue
            
        # Renombrar segunda columna 'Name' si existe
        name_indices = [i for i, col in enumerate(df.columns) if col == 'Name']
        if len(name_indices) > 1:
            cols = list(df.columns)
            cols[name_indices[1]] = 'Name1'
            df.columns = cols
        
        # Limpiar datos y hacer merge con claves
        df = df.dropna(subset=['Name']).loc[:, ~df.columns.duplicated()]
        keys = key_df[key_df['S-A'] == tipo]
        
        if not keys.empty:
            # Determinar columnas para el merge según disponibilidad
            merge_columns = ['Name']  # Name siempre está presente
            
            # Agregar columnas opcionales si existen en ambos DataFrames
            if 'Monitoring Type' in df.columns and 'Monitoring Type' in keys.columns:
                merge_columns.append('Monitoring Type')
            if 'Monitoring Address' in df.columns and 'Monitoring Address' in keys.columns:
                merge_columns.append('Monitoring Address')
            
            # Agregar 'Key' a las columnas a obtener de keys
            columns_from_keys = merge_columns + ['Key']
            
            merged = pd.merge(df, keys[columns_from_keys], 
                            on=merge_columns, how='left')
            merged['Scada Key'] = merged['Key'].astype(str)
            merged.drop(columns=['Key'], inplace=True)
            resultados[tipo] = merged
        else:
            resultados[tipo] = df
    
    # Agregar ICCP si existe
    iccp_df = data_dict.get('ICCP', pd.DataFrame())
    if not iccp_df.empty:
        resultados['ICCP'] = iccp_df.loc[:, ~iccp_df.columns.duplicated()]
    
    # Crear carpetas y guardar archivo
    carpeta_load = os.path.join(_rt(), 'out', 'Load')
    os.makedirs(carpeta_load, exist_ok=True)
    archivo_excel = os.path.join(carpeta_load, 'Señales_with_keys.xlsx')
    
    with pd.ExcelWriter(archivo_excel) as writer:
        for nombre, df in resultados.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
            Logger.write_log().log_all('info', f"Hoja {nombre} guardada con {len(df)} registros", logger_console, logger)
    
    Logger.write_log().log_all('info', f"Archivo Excel guardado: {archivo_excel}", logger_console, logger)

def asignar_claves_cal(datafrem, scada_s, scada_a):
    # Asegurarse de que la columna 'Key' exista y sea tipo objeto
    datafrem = datafrem.copy()  # Crear copia explícita para evitar SettingWithCopyWarning
    if 'Key' not in datafrem.columns:
        datafrem['Key'] = pd.NA
    datafrem['Key'] = datafrem['Key'].astype('object')
    new_keys_list = []
    for index, row in datafrem.iterrows():
        station = row['Station'].split(':')
        station = station[0]
        if row['S-A'] == 'STATUS':
            station = f"22{int(station):03d}"
            filtered_keys = scada_s.loc[scada_s['Key'].astype(str).str.startswith(station), 'Key']
        if row['S-A'] == 'ANALOG':
            station = f"24{int(station):03d}"
            filtered_keys = scada_a.loc[scada_a['Key'].astype(str).str.startswith(station), 'Key']
        # Filtrar claves que comienzan con el patrón
        if not filtered_keys.empty:
            suffixes_from_scada = filtered_keys.astype(str).str[-3:].tolist()
        else:
            suffixes_from_scada = []

        suffixes_from_new = [str(key)[-3:] for key in new_keys_list if str(key).startswith(station)]
        all_suffixes = sorted(set(suffixes_from_scada + suffixes_from_new))
        existing_keys = desconvertir_lista(all_suffixes)

        if existing_keys:
            all_possible = set(range(int(existing_keys[0]), int(existing_keys[-1]) + 1))
            missing_keys = sorted(all_possible - set(existing_keys))
        else:
            missing_keys = []

        if missing_keys:
            new_suffix = convertir_numero(missing_keys[0])
        else:
            new_suffix = convertir_numero(int(max(existing_keys)) + 1) if existing_keys else "001"

        new_key = station + new_suffix
        new_keys_list.append(new_key)
        datafrem.at[index, 'Key'] = new_key
    return datafrem

def asignar_claves_manuales(datafrem, scada_s, scada_a):
    """
    Asigna claves para señales manuales (M_IND).
    - STATUS: 12 + station (3 dígitos) + consecutivo
    - ANALOG: 14 + station (3 dígitos) + consecutivo
    """
    # Crear copia explícita para evitar SettingWithCopyWarning
    datafrem = datafrem.copy()
    if 'Key' not in datafrem.columns:
        datafrem['Key'] = pd.NA
    datafrem['Key'] = datafrem['Key'].astype('object')
    new_keys_list = []
    
    for index, row in datafrem.iterrows():
        # Extraer número de station
        station = row['Station'].split(':')[0]
        
        # Determinar prefijo según tipo STATUS/ANALOG
        if row['S-A'] == 'STATUS':
            prefix = f"12{int(station):03d}"
            filtered_keys = scada_s.loc[scada_s['Key'].astype(str).str.startswith(prefix), 'Key']
        elif row['S-A'] == 'ANALOG':
            prefix = f"14{int(station):03d}"
            filtered_keys = scada_a.loc[scada_a['Key'].astype(str).str.startswith(prefix), 'Key']
        else:
            Logger.write_log().log_all('warning', f"Tipo S-A desconocido para señal manual: {row['S-A']}", logger_console, logger)
            continue
        
        # Obtener sufijos existentes en SCADA
        if not filtered_keys.empty:
            suffixes_from_scada = filtered_keys.astype(str).str[-3:].tolist()
        else:
            suffixes_from_scada = []

        # Sufijos de claves ya generadas en este proceso
        suffixes_from_new = [str(key)[-3:] for key in new_keys_list if str(key).startswith(prefix)]
        all_suffixes = sorted(set(suffixes_from_scada + suffixes_from_new))
        existing_keys = desconvertir_lista(all_suffixes)

        # Buscar hueco o siguiente consecutivo
        if existing_keys:
            all_possible = set(range(int(existing_keys[0]), int(existing_keys[-1]) + 1))
            missing_keys = sorted(all_possible - set(existing_keys))
        else:
            missing_keys = []

        if missing_keys:
            new_suffix = convertir_numero(missing_keys[0])
        else:
            new_suffix = convertir_numero(int(max(existing_keys)) + 1) if existing_keys else "001"

        new_key = prefix + new_suffix
        new_keys_list.append(new_key)
        datafrem.at[index, 'Key'] = new_key
    
    return datafrem

def buscar_keys_usar_en_scada(df, columna_tipo, columna_rtu, dicc):
    """
    Asigna keys disponibles del diccionario al DataFrame según el tipo y RTU.
    Retorna dos DataFrames:
    - df_con_keys: igual al df original pero con columnas 'Key' y 'PointAddress' solo para las filas asignadas
    - df_sin_keys: igual al df original, solo las filas sin key asignada
    """
    df = df.copy()
    df['Key'] = None
    df['PointAddress'] = None
    keys_usadas = set()
    indices_con_key = []
    indices_sin_key = []
    for idx, row in df.iterrows():
        prefix = str(row[columna_tipo]) + str(row[columna_rtu]).zfill(3)
        posibles_keys = [k for k in dicc if k.startswith(prefix) and k not in keys_usadas]
        if posibles_keys:
            key = posibles_keys[0]
            df.at[idx, 'Key'] = key
            df.at[idx, 'PointAddress'] = dicc[key]
            keys_usadas.add(key)
            indices_con_key.append(idx)
        else:
            indices_sin_key.append(idx)
    df_con_keys = df.loc[indices_con_key].copy()
    df_sin_keys = df.loc[indices_sin_key].copy()
    return df_con_keys, df_sin_keys

def validaciones(dfs, ioa):
    errores = []
    Logger.write_log().log_all('info', "Iniciando validaciones de duplicados y valores", logger_console, logger)
    status = dfs.get('STATUS', pd.DataFrame()).dropna(subset=['Name']).copy()
    analog = dfs.get('ANALOG', pd.DataFrame()).dropna(subset=['Name']).copy()
    status = status.loc[:, ~status.columns.duplicated()]
    analog = analog.loc[:, ~analog.columns.duplicated()]
    
    # Agregar columna de identificación de hoja antes de combinar
    status['_sheet_name'] = 'STATUS'
    status['_row_number'] = range(1, len(status) + 1)
    analog['_sheet_name'] = 'ANALOG'
    analog['_row_number'] = range(1, len(analog) + 1)
    
    df_combinado = pd.concat([status, analog], ignore_index=True)

    # Verificar si todas las señales son de tipo Manual o Cálculo (no requieren RTU)
    tipos_sin_rtu = ['M_IND', 'C_IND', 'C_ANLG']
    if 'Type' in df_combinado.columns:
        todos_sin_rtu = df_combinado['Type'].notna() & df_combinado['Type'].isin(tipos_sin_rtu)
        solo_señales_sin_rtu = todos_sin_rtu.all()
    else:
        solo_señales_sin_rtu = False

    # Validación de columnas con ':' y valor antes de los dos puntos
    # Definir columnas específicas por hoja
    columnas_comunes = ['Station', 'AOR Group', 'Alarm Group']
    columnas_status = columnas_comunes + ['State Table']
    columnas_analog = columnas_comunes + ['Scale Factor', 'Units']
    
    # Para STATUS: agregar 'State Table for Controls' solo si hay comandos
    if 'Command Type' in status.columns and status['Command Type'].notna().any():
        columnas_status.append('State Table for Controls')
    
    # RTU solo se valida si NO son todas señales sin RTU
    if not solo_señales_sin_rtu:
        columnas_status.insert(0, 'RTU')
        columnas_analog.insert(0, 'RTU')
    
    # Validar cada hoja con sus columnas específicas
    for sheet_name, df_sheet in [('STATUS', status), ('ANALOG', analog)]:
        if sheet_name == 'STATUS':
            columnas_validar = columnas_status
        else:  # ANALOG
            columnas_validar = columnas_analog
            
        for col in columnas_validar:
            if col in df_sheet.columns:
                # Solo omitir filas donde Name sea vacío (ya filtrado al inicio), validar todas las demás celdas
                for idx, val in df_sheet[col].items():
                    # Para 'State Table for Controls', solo validar filas que tienen Command Type
                    if col == 'State Table for Controls' and 'Command Type' in df_sheet.columns:
                        command_type = df_sheet.at[idx, 'Command Type']
                        if pd.isna(command_type) or command_type == '':
                            continue  # Saltar validación si no hay Command Type
                    
                    # Validar si la celda está vacía o tiene formato incorrecto
                    if pd.isna(val) or val == '' or not isinstance(val, str) or ':' not in val or val.split(':', 1)[0].strip() == '':
                        # Obtener fila original (idx + 1 porque se eliminó el encabezado)
                        row_number = idx + 1
                        if pd.isna(val) or val == '':
                            errores.append(
                                f"Hoja '{sheet_name}', Fila {row_number}: columna '{col}' está vacía"
                            )
                        else:
                            errores.append(
                                f"Hoja '{sheet_name}', Fila {row_number}: columna '{col}' no contiene ':' o no es texto o no tiene valor antes de ':'"
                            )
    
    # Validar unicidad de RTU SOLO si hay señales que requieren RTU
    rtu_valor = None  # Inicializar variable
    if not solo_señales_sin_rtu:
        if 'RTU' not in df_combinado.columns or df_combinado['RTU'].isna().all():
            error_msg = "Error: No hay valores válidos de RTU en el DataFrame (requerido para señales FEP)"
            errores.append(error_msg)
            Logger.write_log().log_all('error', error_msg, logger_console, logger)
            return None, errores
            
        rtu_valores = set(df_combinado['RTU'].dropna().astype(str).str.split(':').str[0])
        if len(rtu_valores) == 1:
            rtu_valor = rtu_valores.pop()
        else:
            error_msg = f"Error: Hay más de un valor de RTU en el DataFrame: {rtu_valores}"
            errores.append(error_msg)
            Logger.write_log().log_all('error', error_msg, logger_console, logger)
            return None, errores  # Retornar aquí también
    else:
        # Si todas son señales sin RTU, no validar RTU
        Logger.write_log().log_all('info', "Todas las señales son de tipo Manual/Cálculo - RTU no requerido", logger_console, logger)

    # Validar duplicados en 'Name' y 'Monitoring Address' omitiendo NaN
    for sheet_name, df in [('STATUS', status), ('ANALOG', analog)]:
        # Validar duplicados en 'Name' considerando Station
        if 'Name' in df.columns:
            # Buscar duplicados de Name
            duplicated_names = df[df['Name'].notna() & df.duplicated(subset=['Name'], keep=False)]
            if not duplicated_names.empty:
                # Agrupar por Name para verificar si están en la misma Station
                for name_value in duplicated_names['Name'].unique():
                    name_rows = duplicated_names[duplicated_names['Name'] == name_value]
                    
                    if 'Station' in name_rows.columns:
                        # Extraer valores de Station (antes de ':')
                        stations = name_rows['Station'].dropna().astype(str).str.split(':').str[0].unique()
                        
                        if len(stations) == 1:
                            # Mismo Station - ahora solo WARNING (no detiene el proceso)
                            warning_msg = f"Nombre duplicado en hoja '{sheet_name}' (misma Station {stations[0]}): {name_value}"
                            Logger.write_log().log_all('warning', warning_msg, logger_console, logger)
                        else:
                            # Diferentes Stations - WARNING
                            warning_msg = f"Nombre duplicado en hoja '{sheet_name}' en diferentes Stations: {name_value} -> {', '.join(stations)}"
                            Logger.write_log().log_all('warning', warning_msg, logger_console, logger)
                    else:
                        # Sin columna Station - WARNING también
                        warning_msg = f"Nombre duplicado en hoja '{sheet_name}' (sin columna Station): {name_value}"
                        Logger.write_log().log_all('warning', warning_msg, logger_console, logger)

        # Validar duplicados en 'Monitoring Address' (mantener lógica original)
        if 'Monitoring Address' in df.columns:
            duplicated = df[df['Monitoring Address'].notna() & df.duplicated(subset=['Monitoring Address'], keep=False)]
            if not duplicated.empty:
                error_msg = f"Duplicados en columna 'Monitoring Address' en hoja '{sheet_name}': {duplicated[['Monitoring Address']].to_dict(orient='records')}"
                errores.append(error_msg)
                Logger.write_log().log_all('error', error_msg, logger_console, logger)

    # Validar IOA duplicadas entre Excel y fEP SOLO para la RTU actual (si existe)
    if rtu_valor is not None:
        try:
            status_rtu = status[status['RTU'].astype(str).str.split(':').str[0] == rtu_valor]
            analog_rtu = analog[analog['RTU'].astype(str).str.split(':').str[0] == rtu_valor]
            ioas_excel = pd.concat([status_rtu['Monitoring Address'], analog_rtu['Monitoring Address']]).dropna()
            ioas_excel = ioas_excel.astype(str).str.strip()
            
            # Obtener IOAs del fEP para la RTU actual
            try:
                rtu_key = int(rtu_valor)  # Intentar convertir a int
            except ValueError:
                # Si no se puede convertir, usar el valor como string
                rtu_key = rtu_valor
                
            ioa_rtu = ioa.get(rtu_key, set())
            ioa_normalizado = set(str(x) for x in ioa_rtu)
            ioas_en_fep = ioa_normalizado.intersection(set(ioas_excel))

            if ioas_en_fep:
                error_msg = f"Las siguientes IOA del Excel ya existen en Fep: {', '.join(ioas_en_fep)}"
                errores.append(error_msg)
                Logger.write_log().log_all('error', error_msg, logger_console, logger)
        except Exception as e:
            error_msg = f"Error en validación de IOAs: {str(e)}"
            errores.append(error_msg)
            Logger.write_log().log_all('error', error_msg, logger_console, logger)
    else:
        Logger.write_log().log_all('info', "Validación de IOAs omitida (no hay señales con RTU)", logger_console, logger)

    # Columnas a validar
    columnas_validar = ['4 seg ins', '1 min ins', '5 min ins', '5 min avg',
                        '1 hor avg', '1 hor max', '1 hor min', 'HRS', '15 min ins']
    
    # Verificar primero si las columnas existen
    columnas_existentes = [col for col in columnas_validar if col in analog.columns]
    if columnas_existentes:
        try:
            # Solo verificar columnas que existen
            analog_temp = analog[columnas_existentes].fillna(0).astype(int).copy()
            
            columnas_con_errores = [col for col in columnas_existentes 
                                    if not analog_temp[col].isin([0, 1]).all()]
            if columnas_con_errores:
                error_msg = f"Columnas con valores distintos de 0 o 1: {', '.join(columnas_con_errores)}"
                errores.append(error_msg)
                Logger.write_log().log_all('error', error_msg, logger_console, logger)
        except Exception as e:
            error_msg = f"Error validando columnas de configuración: {str(e)}"
            errores.append(error_msg)
            Logger.write_log().log_all('error', error_msg, logger_console, logger)
    
    # Guardar errores en un archivo temporal para fácil lectura
    if errores:
        error_file = os.path.join(_rt(), 'out', 'validacion_errores.txt')
        os.makedirs(os.path.dirname(error_file), exist_ok=True)
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write("Se encontraron los siguientes errores en las validaciones:\n")
            for err in errores:
                f.write(f"- {err}\n")
                
        # Solo escribir al log, no imprimir a la consola aquí
        Logger.write_log().log_all('error', "Se encontraron errores en las validaciones", logger_console, logger)
        return None, errores

    # Limpiar las columnas temporales antes de retornar
    if '_sheet_name' in status.columns:
        status.drop(columns=['_sheet_name', '_row_number'], inplace=True)
    if '_sheet_name' in analog.columns:
        analog.drop(columns=['_sheet_name', '_row_number'], inplace=True)
    
    # Actualizar el diccionario dfs con los DataFrames limpios
    dfs['STATUS'] = status
    dfs['ANALOG'] = analog
    
    Logger.write_log().log_all('info', "Validaciones completadas correctamente", logger_console, logger)
    return dfs, []

def asignar_claves_iccp(df, ruta_scada):
    Logger.write_log().log_all('info', "Iniciando asignación de claves ICCP", logger_console, logger)
    try:
        # Leer archivo 36_16 con manejo de archivo inexistente
        archivo_36_16 = os.path.join(ruta_scada, '36_16.csv')
        if os.path.exists(archivo_36_16):
            df_36_16 = pd.read_csv(archivo_36_16, usecols=['REC_KEY'], encoding='utf-8', low_memory=False)
            # Filtrar solo claves ICCP (11 y 13)
            df_36_16 = df_36_16[df_36_16['REC_KEY'].astype(str).str.startswith(('11', '13'))]
        else:
            df_36_16 = pd.DataFrame(columns=['REC_KEY'])
            Logger.write_log().log_all('warning', f"Archivo {archivo_36_16} no existe, se usará un DataFrame vacío", logger_console, logger)
        
        # Verificar si existe la columna Import ICCP Name
        if 'Import ICCP Name' not in df.columns:
            Logger.write_log().log_all('warning', "No existe columna 'Import ICCP Name' en el DataFrame", logger_console, logger)
            return df, pd.DataFrame()
        
        # Separar señales con/sin ICCP
        df_con_iccp = df[df['Import ICCP Name'].notna()].copy()
        df_sin_iccp = df[df['Import ICCP Name'].isna()].copy()
        
        if df_con_iccp.empty:
            Logger.write_log().log_all('info', "No hay señales con Import ICCP Name", logger_console, logger)
            return pd.DataFrame(), df_sin_iccp
        
        # Verificar columnas necesarias
        if 'Station' not in df_con_iccp.columns or 'S-A' not in df_con_iccp.columns:
            Logger.write_log().log_all('error', "Faltan columnas requeridas (Station o S-A)", logger_console, logger)
            return pd.DataFrame(), df
        
        # Crear prefijos de manera más segura
        df_con_iccp['numero_station'] = df_con_iccp['Station'].astype(str).str.split(':').str[0].str.zfill(3)
        df_con_iccp['prefijo'] = df_con_iccp['S-A'].map({'STATUS': '11', 'ANALOG': '13'}) + df_con_iccp['numero_station']
        df_con_iccp.drop(columns=['Import ICCP Name'], inplace=True)

        # Preparar diccionario de sufijos existentes por prefijo
        rec_keys = df_36_16['REC_KEY'].astype(str).tolist() if not df_36_16.empty else []
        sufijos_por_prefijo = {}
        
        # Procesar cada prefijo único
        for prefijo in df_con_iccp['prefijo'].dropna().unique():
            claves_con_prefijo = [key[-3:] for key in rec_keys if key.startswith(prefijo)]
            
            # Convertir sufijos de manera segura
            sufijos_numericos = []
            for sufijo in claves_con_prefijo:
                try:
                    if sufijo.isdigit() and len(sufijo) == 3:
                        sufijos_numericos.append(int(sufijo))
                    elif len(sufijo) == 3 and sufijo[0].isalpha() and sufijo[1:].isdigit():
                        letra = sufijo[0]
                        resto = int(sufijo[1:])
                        num = (ord(letra) - 65) * 100 + 1000 + resto
                        sufijos_numericos.append(num)
                except Exception as e:
                    Logger.write_log().log_all('warning', f"Error al procesar sufijo '{sufijo}': {e}", logger_console, logger)
                    continue
            
            sufijos_por_prefijo[prefijo] = set(sufijos_numericos)
        
        # Asignar claves de manera segura
        df_con_iccp['Key'] = None
        contador_por_prefijo = {}
        
        for idx, row in df_con_iccp.iterrows():
            prefijo = row['prefijo']
            if pd.isna(prefijo):
                continue
                
            # Obtener sufijos ya usados para este prefijo
            sufijos_usados = sufijos_por_prefijo.get(prefijo, set()) | contador_por_prefijo.get(prefijo, set())
            contador_por_prefijo.setdefault(prefijo, set())
            
            # Buscar el siguiente sufijo disponible
            for i in range(1, 4000):
                if i not in sufijos_usados:
                    nuevo_sufijo = i
                    contador_por_prefijo[prefijo].add(nuevo_sufijo)
                    break
            else:
                Logger.write_log().log_all('warning', f"No se encontraron sufijos disponibles para {prefijo}", logger_console, logger)
                continue
                
            # Generar la clave completa
            df_con_iccp.at[idx, 'Key'] = f"{prefijo}{convertir_numero(nuevo_sufijo)}"
        
        df_con_iccp.drop(columns=['prefijo', 'numero_station'], inplace=True)
        
        # Contar claves generadas
        keys_generadas = df_con_iccp['Key'].notna().sum()
        Logger.write_log().log_all('info', f"Keys ICCP generadas: {keys_generadas}", logger_console, logger)
        Logger.write_log().log_all('info', f"Señales sin ICCP:  {len(df_sin_iccp)} ", logger_console, logger)
        return df_con_iccp, df_sin_iccp
    
        
    except Exception as e:
        error_detalle = traceback.format_exc()
        Logger.write_log().log_all('error', f"Error en asignación ICCP: {str(e)}\n{error_detalle}", logger_console, logger)
        raise
    
# =============================
# Main
# =============================
def main():
    args = get_args()
    ruta_excel = args.archivo_excel
    empresa = args.empresa
    Logger.write_log().log_all('info', f"Inicio de proceso principal con archivo: {ruta_excel}", logger_console, logger)
    # Inicializar acumuladores de señales que se van a crear nuevas en 32_27
    total_nuevas_signals = 0

    rt = _rt()
    ruta_scada = _scada_path(rt, empresa, args.dominio)

    data = pd.read_csv(os.path.join(ruta_scada, '32_27.csv'), encoding='ISO-8859-1', low_memory=False)

    # Normalizar nombre de columna 'record'
    for col in data.columns:
        if col.lower() in ['record', '#record']:
            data = data.rename(columns={col: 'record'})
            break

    scada_status = pd.read_csv(os.path.join(ruta_scada, '10_4.csv'), encoding='ISO-8859-1', low_memory=False)
    scada_analogs = pd.read_csv(os.path.join(ruta_scada, '10_5.csv'), encoding='ISO-8859-1', low_memory=False)
    # Leer y procesar el archivo 32_10 para usar claves que existen en fep pero no tienen destination_key
    df_32_10 = pd.read_csv(os.path.join(ruta_scada, '32_10.csv'),usecols=['Key', 'DestinationKey', 'PointAddress','IntParms','pRTU'],
        encoding='ISO-8859-1',low_memory=False)
    # Filtra IntParms válidos y conviértelos a int
    df_32_10 = df_32_10.dropna(subset=['IntParms'])
    df_32_10 = df_32_10[df_32_10['IntParms'].astype(str).str.strip() != '']
    df_32_10['IntParms'] = df_32_10['IntParms'].astype(float).astype(int)
    # Agrupa por pRTU y crea el diccionario
    rtu_to_intparms = df_32_10.groupby('pRTU')['IntParms'].apply(set).to_dict()
    
    # Filtrar filas donde DestinationKey esté vacío o nulo
    df_32_10 = df_32_10[df_32_10['DestinationKey'].isna() |(df_32_10['DestinationKey'].astype(str).str.strip() == '')]
    # Filtrar filas donde Key comience por '01', '02', '03' o '04'
    df_32_10 = df_32_10[ df_32_10['Key'].astype(str).str.startswith(('01', '02', '03', '04'))]
    # Crear el diccionario Key -> PointAddress
    diccionario_key_pointaddress = dict(zip(df_32_10['Key'].astype(str), df_32_10['PointAddress'].astype(int)))
    
    dfs = leer_hojas_excel(ruta_excel)
    df_validado, lista_errores = validaciones(dfs, rtu_to_intparms)
    if df_validado is not None:
        Logger.write_log().log_all('info', "Validaciones pasadas, procesando datos...", logger_console, logger)
        df_combinado = procesar_dataframes(df_validado)
        df_combinado = extraer_rtu(df_combinado)
        df_combinado = mapear_tipos_monitoreo(df_combinado)
        df_señales_iccp, df_combinado = asignar_claves_iccp(df_combinado, ruta_scada)
        # Dividir dataframes por tipo de monitoreo
        mapa_inicio_tipo = {'DP': 2.0, 'SP': 1.0, 'MV': 3.0, 'ST': 4.0}
        df_nuevo_count = pd.DataFrame()
        dfs_procesados = []
        
        # Validar que haya señales para procesar (sin ICCP)
        if df_combinado.empty:
            Logger.write_log().log_all('warning', 'Todas las señales tienen Import ICCP Name, no hay señales FEP para procesar', logger_console, logger)
            tipos_presentes = []
            rtu = None
        else:
            tipos_presentes = df_combinado['Monitoring Type'].dropna().unique()
            # Obtener RTU solo si existe y no es None
            if 'pRTU' in df_combinado.columns and df_combinado['pRTU'].notna().any():
                rtu = float(df_combinado['pRTU'].dropna().iloc[0])
            else:
                rtu = None
                Logger.write_log().log_all('info', 'No hay RTU en las señales (manuales/cálculo)', logger_console, logger)

        # Copiar counts originales del RTU actual desde data
        if rtu is not None:
            row_data = data[data['record'] == rtu]
            if not row_data.empty:
                for col in row_data.columns:
                    if col.startswith('Count'):
                        df_nuevo_count[col] = [row_data.iloc[0][col]]
                df_nuevo_count['#Record'] = [int(rtu)]
        # Procesar y sobrescribir counts solo para los tipos presentes
        for tipo in tipos_presentes:
            df_tipo = df_combinado[df_combinado['Monitoring Type'] == tipo]
            df_tipo_con_keys, df_tipo = buscar_keys_usar_en_scada(df_tipo, 'Typex', 'pRTU', diccionario_key_pointaddress)
            # df_tipo contiene SOLO las que requieren nueva clave
            total_nuevas_signals += len(df_tipo)   
            valor_inicio, valor_n_count = buscar_valores(df_tipo, data, mapa_inicio_tipo[tipo], rtu)
            df_nuevo_count[valor_n_count[0]] = [valor_n_count[1]]
            df_nuevo_count['#Record'] = [int(rtu)]
            df_procesado = crear_claves_scada(df_tipo, 'Typex', 'pRTU', valor_inicio)
            df_tipo_total = pd.concat([df_tipo_con_keys, df_procesado], ignore_index=True)
            dfs_procesados.append(df_tipo_total)

        # Procesar señales de cálculo (C_IND, C_ANLG)
        df_filas_calculos = df_combinado[(df_combinado['Type'] == 'C_IND') | (df_combinado['Type'] == 'C_ANLG')]
        if not df_filas_calculos.empty:
            Logger.write_log().log_all('info', f"Procesando {len(df_filas_calculos)} señales de cálculo", logger_console, logger)
        data_calculos = asignar_claves_cal(df_filas_calculos, scada_status, scada_analogs)

        # Procesar señales manuales (M_IND)
        df_filas_manuales = df_combinado[df_combinado['Type'] == 'M_IND']
        if not df_filas_manuales.empty:
            Logger.write_log().log_all('info', f"Procesando {len(df_filas_manuales)} señales manuales (M_IND)", logger_console, logger)
        data_manuales = asignar_claves_manuales(df_filas_manuales, scada_status, scada_analogs)

        # Procesar señales tipo 41 (sin Monitoring Type, excepto cálculos y manuales)
        df_filas_41 = df_combinado[(df_combinado['Monitoring Type'].isna()) &
                                    (df_combinado['Type'] != 'C_IND') &
                                    (df_combinado['Type'] != 'C_ANLG') &
                                    (df_combinado['Type'] != 'M_IND')]
        if not df_filas_41.empty:
            Logger.write_log().log_all('info', f"Procesando {len(df_filas_41)} señales tipo 41", logger_console, logger)
        df_filas_41 = asignar_claves_41(df_filas_41, scada_status)

        # Convertir todas las columnas Count a enteros antes de guardar (solo si tiene datos)
        if not df_nuevo_count.empty:
            for col in df_nuevo_count.columns:
                if col.startswith('Count'):
                    df_nuevo_count[col] = df_nuevo_count[col].astype('Int64').fillna(0).astype(int)
            df_nuevo_count = procesar_nuevos_count(df_nuevo_count)
            df_nuevo_count.insert(0, 'RTU_DEFN', None)
            df_nuevo_count.insert(0, '27', None)
        else:
            Logger.write_log().log_all('info', 'No se generó df_nuevo_count (no hay señales FEP con RTU)', logger_console, logger)

        # Combinar dataframes procesados - validar que haya datos
        if not dfs_procesados:
            Logger.write_log().log_all('warning', 'No hay señales FEP para procesar (dfs_procesados vacío)', logger_console, logger)
            df_combinado1 = pd.DataFrame()
        else:
            df_combinado1 = pd.concat(dfs_procesados, ignore_index=True)
        
        # Incluir df_señales_iccp solo si no está vacío
        # Combinar solo los DataFrames que no estén vacíos
        dfs_para_keys = [df for df in [df_combinado1, df_filas_41, data_calculos, data_manuales] if not df.empty]
        if not df_señales_iccp.empty:
            dfs_para_keys.append(df_señales_iccp)
        
        if dfs_para_keys:
            df_total_keys = pd.concat(dfs_para_keys, ignore_index=True)
        else:
            Logger.write_log().log_all('error', 'No hay datos para procesar (todos los DataFrames vacíos)', logger_console, logger)
            sys.exit(1)
        
        # df_combinado_final solo para scan_data (señales FEP)
        if df_combinado1.empty:
            Logger.write_log().log_all('warning', 'No se generará scan_data.csv (no hay señales FEP)', logger_console, logger)
            df_combinado_final = pd.DataFrame()
        else:
            df_combinado_final = df_combinado1.copy()

        merge_and_save_excel(dfs, df_total_keys)

        # Preparación final del DataFrame solo si hay datos FEP
        if not df_combinado_final.empty:
            # Asignar secuencia descendente de negativos: -1, -2, -3, ... por fila
            df_combinado_final['#Record'] = list(range(-1, -len(df_combinado_final) - 1, -1))
            df_combinado_final['Indic'] = '1'
            df_combinado_final['DestinationKey'] = df_combinado_final['Key']
            df_combinado_final['Name'] = df_combinado_final['Key']
            df_combinado_final['IntParms;0'] = df_combinado_final['Monitoring Address']
            df_combinado_final['IntParms;1'] = df_combinado_final['Monitoring Address']

            # Seleccionar y formatear columnas
            columnas_salida = [
                '#Record', 'Indic', 'ProtocolType', 'Key', 'pRTU',
                'PointAddress', 'DestinationKey', 'IntParms;0',
                'IntParms;1', 'Name'
            ]
            df_combinado_final = df_combinado_final[columnas_salida]

            # Añadir comillas a columnas específicas
            columnas_comillas = ['Key', 'DestinationKey', 'Name']
            for col in columnas_comillas:
                df_combinado_final[col] = df_combinado_final[col].apply(lambda x: f'"{x}"')

            df_combinado_final.insert(0, 'SCAN_DATA', None)
            df_combinado_final.insert(0, '10', None)

        # Salidas SIEMPRE en CWD/out/Load
        carpeta_out = os.path.join(rt, 'out')
        os.makedirs(carpeta_out, exist_ok=True)
        carpeta_load = os.path.join(carpeta_out, 'Load')
        os.makedirs(carpeta_load, exist_ok=True)

        archivo_salida = os.path.join(carpeta_load, "scan_data.csv")
        archivo_counts_nuevos = os.path.join(carpeta_load, "Nuevos_counts.csv")

        # Guardar archivos solo si hay datos
        if not df_combinado_final.empty:
            Logger.write_log().log_all('info', f"Guardando archivo: {archivo_salida}", logger_console, logger)
            if '#Record' in df_combinado_final.columns:
                df_combinado_final['#Record'] = df_combinado_final['#Record'].apply(lambda x: int(x) if pd.notna(x) and str(x).replace('.', '', 1).isdigit() else x)
            df_combinado_final.to_csv(archivo_salida, index=False, quoting=csv.QUOTE_NONE, escapechar=' ')
        else:
            Logger.write_log().log_all('warning', "No se generó scan_data.csv (no hay señales FEP)", logger_console, logger)
        
        if total_nuevas_signals > 0:
            Logger.write_log().log_all('info', f"Guardando archivo: {archivo_counts_nuevos}", logger_console, logger)
            df_nuevo_count.to_csv(archivo_counts_nuevos, index=False, quoting=csv.QUOTE_NONE, escapechar=' ')
            Logger.write_log().log_all('info', "Se generó Nuevos_counts.csv (hubo nuevas señales).", logger_console, logger)
        else:
            Logger.write_log().log_all('info', "No hubo nuevas señales; se omite Nuevos_counts.csv.", logger_console, logger)
        Logger.write_log().log_all('info', f"Procesamiento completado. Archivo de salida guardado en {carpeta_load}", logger_console, logger)
        print(f"Procesamiento completado. Archivo de salida guardado en {carpeta_load}")
        return 0  # Código de salida para éxito
    else:
        # Construir mensaje de error una sola vez
        errores_msg = "Se encontraron los siguientes errores en las validaciones:\n"
        for err in lista_errores:
            errores_msg += f"- {err}\n"
        
        # Solo escribir al log y mostrar mensaje resumido en la consola
        Logger.write_log().log_all('error', errores_msg, logger_console, logger)
        print("Validación fallida. Revisa los detalles en el archivo de errores.")
        sys.exit(2)  # Código especial para errores de validación

if __name__ == "__main__":
    sys.exit(main())

