import os
import sys
import pandas as pd
import numpy as np
import re
import Leer_unifilares
try:
    # cuando se ejecuta como paquete: python -m scripts.buscar_key
    from scripts import _Logger as Logger
except Exception:
    try:
        # cuando se ejecuta como script “plano”
        import _Logger as Logger
    except Exception:
        # ultimo recurso: agregar la carpeta "scripts" al sys.path
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger

def build_page_dataframe(unifilar_data):
    size_list = unifilar_data.get('DisplaySize', [])
    page_dict = unifilar_data.get('PageList', {})
    if not size_list or not page_dict:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(page_dict, orient='index').copy()
    size = float(size_list[0])
    df['Size'] = size
    df[['ZoomPercent', 'AspectRatio']] = df[['ZoomPercent', 'AspectRatio']].astype(float)
    df[['CenterX', 'CenterY']] = df['Center'].str.split(',', expand=True).astype(float)
    df['CenterY'] = size - df['CenterY']
    df['Height'] = size * df['ZoomPercent'] / 100
    df['Width'] = df['Height'] / df['AspectRatio']
    df['LeftLimit'] = df['CenterX'] - df['Width'] / 2
    df['RightLimit'] = df['CenterX'] + df['Width'] / 2
    df['TopLimit'] = df['CenterY'] - df['Height'] / 2
    df['BottomLimit'] = df['CenterY'] + df['Height'] / 2
    return df

def extract_coordinates(location):
    try:
        return tuple(map(float, str(location).strip('() ').split(',')[:2]))
    except Exception:
        return (np.nan, np.nan)

def assign_voltage_level(x, y, page_df):
    required_cols = {'LeftLimit', 'RightLimit', 'TopLimit', 'BottomLimit', 'Name'}
    if page_df.empty or not required_cols.issubset(page_df.columns):
        return 'SinNivelDeTension'
    mask = (
        (page_df['LeftLimit'] <= x) & (x <= page_df['RightLimit']) &
        (page_df['TopLimit'] <= y) & (y <= page_df['BottomLimit'])
    )
    result = page_df.loc[mask, 'Name']
    return result.iloc[0] if not result.empty else 'SinNivelDeTension'

def extract_keys(obj, opennet_dict=None):
    data_link = obj.get('Data Link', '')
    data_key_match = re.search(r'^SCADA/(ANALOG|STATUS).*key/([\w]+)', data_link)
    data_key = data_key_match.group(2) if data_key_match else None

    color_link = obj.get('Color Link', '')
    color_key_match = re.search(r'^SCADA/(ANALOG|STATUS).*key/([\w]+)', color_link)
    if color_key_match:
        color_key = color_key_match.group(2)
    else:
        record_match = re.search(r'^COLOR_OPENNET.*(?:record|key)/(\d+)', color_link)
        if record_match and opennet_dict is not None:
            record_number = int(record_match.group(1))
            color_key = opennet_dict.get(record_number, None)
        else:
            color_key = None

    return data_key, color_key

def process_unifilar_file(file_path, file_name, opennet_dict, logger=None, logger_console=None):
    if logger and logger_console:
        Logger.write_log().log_all('debug', f'Leyendo unifilar {file_name}', logger_console, logger)

    unifilar_data = Leer_unifilares.leer_archivo(file_path)
    page_df = build_page_dataframe(unifilar_data)

    object_list = unifilar_data.get('ObjectList', {})
    processed_data = []

    for obj_id, attributes in object_list.items():
        attributes = attributes.copy()
        attributes['ObjectID'] = obj_id
        attributes['Archivo'] = file_name

        x, y = extract_coordinates(attributes.get('Location'))
        attributes['NivelDeTension'] = assign_voltage_level(x, y, page_df)

        data_key, color_key = extract_keys(attributes, opennet_dict)
        attributes['Data Key'] = data_key
        attributes['Color Key'] = color_key
        attributes.pop('Data Link', None)
        attributes.pop('Color Link', None)

        processed_data.append(attributes)

    result_df = pd.DataFrame(processed_data)
    ordered_cols = ['Archivo', 'NivelDeTension', 'Data Key', 'Color Key'] + \
                   [col for col in result_df.columns if col not in ['Archivo', 'NivelDeTension', 'Data Key', 'Color Key']]
    return result_df[ordered_cols]

def conver_unifilares_to_csv(empresa, logger, logger_console):
    cwd = os.getcwd()
    base_dir   = os.path.abspath(os.path.join(cwd, 'out', empresa))
    odstxt_dir = os.path.join(base_dir, "ODSTXT")
    scada_path = os.path.join(base_dir, "SCADA", "8_7.csv")

    Logger.write_log().log_all('info', f'Inicia procesamiento unifilar {empresa}', logger_console, logger)

    try:
        opennet_status = pd.read_csv(scada_path, encoding='ISO-8859-1')
        opennet_dict = dict(zip(opennet_status["#record"], opennet_status["pSCADA"]))
        Logger.write_log().log_all('info', 'Archivo SCADA cargado', logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all('error', f'Error al cargar SCADA: {e}', logger_console, logger)
        return

    dataframes = []
    try:
        archivos = os.listdir(odstxt_dir)
    except Exception as e:
        Logger.write_log().log_all('error', f'Error al listar {odstxt_dir}: {e}', logger_console, logger)
        return

    for archivo_txt in archivos:
        if archivo_txt.lower().endswith('.txt'):
            file_path = os.path.join(odstxt_dir, archivo_txt)
            Logger.write_log().log_all('info', f'Procesando {archivo_txt}', logger_console, logger)
            try:
                final_dataframe = process_unifilar_file(file_path, archivo_txt, opennet_dict, logger, logger_console)
                dataframes.append(final_dataframe)
            except Exception as e:
                Logger.write_log().log_all('warning', f'Error al procesar {archivo_txt}: {e}', logger_console, logger)

    if dataframes:
        df_total = pd.concat(dataframes, ignore_index=True)
        output_path = os.path.join(odstxt_dir, "unifilares_procesados.csv")
        df_total.to_csv(output_path, index=False)
        Logger.write_log().log_all('info', f'Archivo combinado guardado en {output_path}', logger_console, logger)
    else:
        Logger.write_log().log_all('warning', 'No .txt files to process', logger_console, logger)
