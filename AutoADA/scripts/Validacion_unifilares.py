import os
import sys
import pandas as pd
import numpy as np
import re
from openpyxl import load_workbook
from collections import defaultdict
import argparse
from datetime import datetime

try:
    # cuando se ejecuta como paquete: python -m scripts.validacion_unifilares
    from scripts import _Logger as Logger
    from scripts.Leer_unifilares import leer_archivo
except Exception:
    try:
        # cuando se ejecuta como script “plano”
        import _Logger as Logger
        from Leer_unifilares import leer_archivo
    except Exception:
        # último recurso: agregar la carpeta "scripts" al sys.path
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger
        from Leer_unifilares import leer_archivo

def _rt():
    """Raíz de trabajo (escritura/lectura) para one-file: el CWD."""
    return os.getcwd()

def get_base_dir(empresa=None):
    if not empresa:
        raise ValueError("Debe especificar el nombre de la empresa con --empresa. No se permite un valor por defecto.")
    return os.path.abspath(os.path.join(_rt(), 'out', empresa))

logger = None
logger_console = None

# =====================
# CARGA DE ARCHIVO UNIFILAR Y DICCIONARIO DE UNIDADES
# =====================
dicc_unit = {
    "0.0": "%.f", "1.0": "kV", "2.0": "A", "3.0": "MW", "4.0": "MVar", "5.0": "MVA",
    "6.0": "kW", "7.0": "kVar", "8.0": "kA", "9.0": "kVA", "10.0": "Hz", "11.0": "ppm",
    "12.0": "°C", "13.0": "V", "14.0": "km", "15.0": "mA", "16.0": "ms", "17.0": "s",
    "18.0": "mOhm", "19.0": "deg", "20.0": "pF", "21.0": "%", "22.0": "kB", "23.0": "MB",
    "24.0": "Ohm", "25.0": "gl", "26.0": "bar"
}

def cargar_datos_scada(SCADA_DIR):
    Logger.write_log().log_all('info', 'Cargando datos SCADA...', logger_console, logger)
    status = pd.read_csv(os.path.join(SCADA_DIR, '10_4.csv'), encoding='ISO-8859-1', low_memory=False)[
        ['Key', 'pStation', 'Name']
    ].rename(columns={'Name': 'Name_key'})
    analogs = pd.read_csv(os.path.join(SCADA_DIR, '10_5.csv'), encoding='ISO-8859-1', low_memory=False)[
        ['Key', 'pStation', 'Name', 'pUNIT']
    ].rename(columns={'Name': 'Name_key'})
    analogs['pUNIT'] = analogs['pUNIT'].astype(str).str.strip().replace(dicc_unit)
    scada = pd.concat([analogs, status]).dropna(subset=['Key'])
    stations = pd.read_csv(os.path.join(SCADA_DIR, '10_2.csv'), encoding='ISO-8859-1', low_memory=False)[
        ['#record', 'Name']
    ]
    opennet_status = pd.read_csv(os.path.join(SCADA_DIR, '8_7.csv'), encoding='ISO-8859-1', low_memory=False)
    Logger.write_log().log_all('info', 'Datos SCADA cargados correctamente.', logger_console, logger)
    return scada.merge(stations, left_on='pStation', right_on='#record', how='left'), opennet_status

# =====================
# FUNCIONES AUXILIARES 
# =====================
def extraer_keys(obj, opennet=None):
    data_link = obj.get('Data Link', '')
    data_key_match = re.search(r'^SCADA/(ANALOG|STATUS).*key/([\w]+)', data_link)
    data_key = data_key_match.group(2) if data_key_match else None
    if opennet is None:
        return {"data_key": data_key}
    color_link = obj.get('Color Link', '')
    color_key_match = re.search(r'^SCADA/(ANALOG|STATUS).*key/([\w]+)', color_link)
    if color_key_match:
        color_key = color_key_match.group(2)
    else:
        record_match = re.search(r'^COLOR_OPENNET.*record/([\w]+)', color_link)
        if record_match:
            record_number = int(record_match.group(1))
            if record_number in opennet["#record"].values:
                pscada_key = opennet.loc[opennet["#record"] == record_number, "pSCADA"].values
                color_key = pscada_key[0] if len(pscada_key) > 0 else None
            else:
                color_key = None
        else:
            color_key = None
    return {
        "data_link": data_link,
        "color_link": color_link,
        "data_key": data_key,
        "color_key": color_key
    }

def analizar_objetos(data, file_name, opennet):
    resultados = []
    # Constantes para evitar repetir strings
    VALID_TYPES = {'SymbolRefObject', 'TextObject'}
    
    for obj_id, obj in data['ObjectList'].items():
        # Early exit si no es tipo válido
        if obj.get('Type') not in VALID_TYPES:
            continue

        keys = extraer_keys(obj, opennet)
        data_key, color_key = keys.get("data_key"), keys.get("color_key")
        
        # Early exit si no hay claves
        if not data_key and not color_key:
            continue

        # Validación de longitud y tipo en una sola línea
        key_candidata = data_key or color_key
        if not (isinstance(key_candidata, str) and len(key_candidata) == 8):
            continue
        # Determinar estado y claves de manera optimizada
        if data_key and color_key:
            key_status = 'Keys iguales' if data_key == color_key else 'Keys diferentes'
            key, key_data_link, key_color_link = data_key, data_key, color_key
        else:
            key_status = 'Solo Data Link' if data_key else 'Solo Color Link'
            key, key_data_link, key_color_link = key_candidata, data_key, color_key

        # Construcción directa del resultado sin variables intermedias
        resultados.append({'File_Name': file_name,'Object_ID': obj_id,'Key': key,
            'Key_data_link': key_data_link,'Key_color_link': key_color_link,
            'Key_Status': key_status,'Symbol_Key': obj.get('Symbol Key', ''),
            'Symbol_Location': obj.get('Location', ''),'Data_Link': keys.get("data_link", ''),
            'Color_Link': keys.get("color_link", ''),'Symbol_Description': obj.get('Symbol_Description', '')})

    return resultados

def aplicar_formato_excel(path):
    try:
        wb = load_workbook(path)
        ws = wb.active
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        wb.save(path)
        logger.info(f'Formato Excel aplicado correctamente: {path}')
    except Exception as e:
        logger.error(f'Error aplicando formato Excel: {e}')

def build_display_dataframe(unifilar):
    size_list = unifilar.get('DisplaySize', [])
    page_list = unifilar.get('PageList', {})
    if not size_list or not page_list:
        return pd.DataFrame(), None
    df = pd.DataFrame.from_dict(page_list, orient='index').copy()
    nombre_display = unifilar.get('DisplayName', [''])[0]
    name_unifilar = re.split(r'[_\.]', nombre_display)[0]
    df['Name'] = df['Name'].apply(lambda x: f"{name_unifilar} {x}")
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

def extract_data(unifilar, objeto, solo_symbol=False, capa1=False):
    objetos = unifilar.get('ObjectList', {})
    tipos_a_incluir = ['SymbolRefObject'] if solo_symbol else (['SymbolRefObject', 'TextObject'] if objeto == 'SymbolRefObject' else [objeto])
    data = []
    for key, value in objetos.items():
        tipo = value.get('Type')
        if tipo not in tipos_a_incluir:
            continue
        keys = extraer_keys(value)
        data_key = keys.get('data_key')
        entry = {
            'ID': key, 'Symbol_Location': None, 'Data_Link': data_key,
            'Symbol Key': value.get('Symbol Key'), 'Tipo': tipo, 'Name_Key': None
        }
        if loc := value.get('Location'):
            coords = [p.strip() for p in loc.strip('() ').split(',')]
            if len(coords) >= 2:
                entry['Symbol_Location'] = f"( {coords[0]}, {coords[1]} )"
        if tipo == 'TextObject':
            if capa1:
                if value.get('Overlay') != '1' or not value.get('String'):
                    continue
                entry['Name_Key'] = value.get('String')
            else:
                entry['Name_Key'] = value.get('String') or value.get('Format String')
        data.append(entry)
    df = pd.DataFrame(data)
    # Definir columnas básicas sin Name_Key para el resultado final
    cols = ['Symbol_Location', 'Data_Link', 'Symbol Key', 'Tipo']
    
    # Solo agregar Name_Key temporalmente si necesitamos procesar TextObjects
    # pero no la incluimos en el resultado final a menos que sea estrictamente necesario
    if not solo_symbol and any(obj.get('Type') == 'TextObject' for obj in objetos.values()):
        # Solo incluir Name_Key si es capa1 (donde se usa para identificar strings específicos)
        if capa1:
            cols.append('Name_Key')
    
    for col in cols:
        df[col] = df.get(col, pd.Series([None]*len(df))).astype(str)
    
    return df[cols]

def group_by_level(df_limits, df_objects):
    df_objects = df_objects.copy()
    df_objects = df_objects[df_objects['Symbol_Location'].notna() & df_objects['Symbol_Location'].str.contains(',')]
    df_objects[['X', 'Y']] = (df_objects['Symbol_Location'].str.strip('()').str.split(',', expand=True).iloc[:, :2].astype(float))
    resultados, asignados = {}, set()
    if isinstance(df_limits, tuple):
        df_limits = df_limits[0]
    if not isinstance(df_limits, pd.DataFrame):
        return {}
    for _, lim in df_limits.iterrows():
        mask = ((df_objects['X'] >= lim['LeftLimit']) & (df_objects['X'] <= lim['RightLimit']) &
                (df_objects['Y'] >= lim['TopLimit']) & (df_objects['Y'] <= lim['BottomLimit']) & (~df_objects.index.isin(asignados)))
        filtrados = df_objects[mask]
        resultados[lim['Name']] = filtrados.drop(columns=['X', 'Y']).reset_index(drop=True)
        asignados.update(filtrados.index)
    no_asignados = df_objects[~df_objects.index.isin(asignados)]
    if not no_asignados.empty:
        no_asignados = no_asignados.drop(columns=['X', 'Y']).copy()
        no_asignados['NivelDeTension'] = 'no tiene nivel de tensión'
        resultados['SinNivelDeTension'] = no_asignados.reset_index(drop=True)
    return {k: v for k, v in resultados.items()}

def pstation_review(dataframes_dict, scada_signal):
    resultados = []
    for nombre_df, df in dataframes_dict.items():
        df = pd.DataFrame(df) if isinstance(df, list) else df
        if 'Data_Link' not in df.columns:
            print(f"Omitido: '{nombre_df}' no tiene la columna 'Data_Link'.")
            continue
        nombre_limpio = " ".join(nombre_df.upper().split())
        merged = df.merge(scada_signal, left_on='Data_Link', right_on='Key', how='left')
        no_coinciden = merged[merged['Key'].isna() | ~merged['Name'].fillna('').apply(
            lambda n: nombre_limpio in " ".join(str(n).upper().split()) or " ".join(str(n).upper().split()) in nombre_limpio
        )].copy()
        if not no_coinciden.empty:
            no_coinciden['Origen'] = nombre_df
            resultados.append(no_coinciden)
    if not resultados:
        return pd.DataFrame()
    df_final = pd.concat(resultados, ignore_index=True).dropna(subset=['Data_Link'])
    df_final = df_final[df_final['Data_Link'].notna() & (df_final['Data_Link'] != '') & (df_final['Data_Link'] != 'None')]
    df_final['Estado'] = 'No coincide SE'
    df_final = df_final.rename(columns={'Name': 'Estacion Scada','Origen': 'Name Unifilar'})
    # Eliminar columnas no deseadas
    columns_to_drop = ['Key', 'Symbol Key', 'Tipo', 'Name Key', 'Name_Key', 'X', 'Y']
    df_final = df_final.drop(columns=[col for col in columns_to_drop if col in df_final.columns])
    return df_final[['Symbol_Location', 'Data_Link', 'Estacion Scada', 'Name Unifilar', 'Estado']]

def add_scada_name(df_symbols, scada_signal):
    df = df_symbols.copy()
    df['Data_Link'] = df['Data_Link'].astype(str)
    scada = scada_signal[['Key', 'Name_key']].copy()
    scada['Key'] = scada['Key'].astype(str)
    return df.merge(scada, left_on='Data_Link', right_on='Key', how='left').drop(columns='Key')

def get_coords(loc):
    try: return tuple(map(float, str(loc).strip('() ').split(',')[:2]))
    except: return np.nan, np.nan

def analizar_proximidad(results2, symbol_keys_filtrar):
    nearest_texts_dict, sin_data_link, sin_texto = {}, {}, []
    
    def calcular_score_posicion(sym_x, sym_y, text_x, text_y):
        """Calcula score basado solo en posición relativa"""
        dist = np.hypot(text_x - sym_x, text_y - sym_y)
        
        # Si está muy lejos, score 0
        if dist > 58:
            return 0
            
        # Score base inverso a la distancia
        score_base = max(0, 100 - dist * 2)
        
        # Calcular desplazamiento relativo
        dx, dy = text_x - sym_x, text_y - sym_y
        
        # Bonus por posición (sin validar tipo de texto)
        bonus_posicion = 0
        
        # Priorizar por posición
        if abs(dy) > abs(dx):  # Movimiento vertical dominante
            if dy > 10:      # Arriba
                bonus_posicion = 60
            elif dy < -10:   # Abajo  
                bonus_posicion = 30
        else:  # Movimiento horizontal dominante
            if dx < -10:     # Izquierda
                bonus_posicion = 50
            elif dx > 10:    # Derecha
                bonus_posicion = 40
        
        return score_base + bonus_posicion
    
    for nivel, df in results2.items():
        if not {'Tipo', 'Symbol Key', 'Symbol_Location'}.issubset(df.columns): continue
        df = df.copy()
        df = df[(df['Tipo'] == 'TextObject') | ((df['Tipo'] == 'SymbolRefObject') & df['Symbol Key'].isin(symbol_keys_filtrar))]
        if 'Data_Link' in df:
            mask_none = (df['Tipo'] == 'SymbolRefObject') & (df['Data_Link'].isna() | df['Data_Link'].eq('') | df['Data_Link'].astype(str).str.lower().isin(['none', 'nan']))
            if mask_none.any():
                df_none = df[mask_none].copy(); df_none['Name Unifilar'] = nivel
                sin_data_link[nivel] = df_none
                df = df[~mask_none]
        df_symbol, df_text = df[df['Tipo'] == 'SymbolRefObject'].copy(), df[df['Tipo'] == 'TextObject'].copy()
        if df_symbol.empty or df_text.empty: continue
        df_symbol[['X', 'Y']] = df_symbol['Symbol_Location'].apply(lambda loc: pd.Series(get_coords(loc)))
        df_text[['X', 'Y']] = df_text['Symbol_Location'].apply(lambda loc: pd.Series(get_coords(loc)))
        df_symbol.dropna(subset=['X', 'Y'], inplace=True)
        df_text.dropna(subset=['X', 'Y'], inplace=True)
        nearest_texts = []
        for _, sym in df_symbol.iterrows():
            sym_x, sym_y = sym['X'], sym['Y']
            
            # Calcular scores para todos los textos
            candidatos = []
            for _, texto in df_text.iterrows():
                # Filtrar textos no deseados: "s" y "25"
                texto_key = str(texto.get('Name_Key', '')).strip().lower()
                if texto_key in ['s', '25']:
                    continue
                    
                score = calcular_score_posicion(sym_x, sym_y, texto['X'], texto['Y'])
                
                if score > 0:
                    candidatos.append({
                        'score': score,
                        'texto': texto
                    })
            
            # Filtrar candidatos que cumplan con los criterios de validación
            def es_texto_valido(texto_key):
                """Valida que el texto no tenga espacios y no supere 10 caracteres"""
                if not texto_key or pd.isna(texto_key):
                    return False
                texto_str = str(texto_key).strip()
                return ' ' not in texto_str and len(texto_str) <= 10
            
            # Seleccionar el mejor candidato que cumpla criterios
            if candidatos:
                # Ordenar candidatos por score descendente
                candidatos_ordenados = sorted(candidatos, key=lambda x: x['score'], reverse=True)
                
                # Buscar el primer candidato que cumpla los criterios
                mejor = None
                for candidato in candidatos_ordenados:
                    texto_key = candidato['texto'].get('Name_Key', '')
                    if es_texto_valido(texto_key):
                        mejor = candidato
                        break
                
                # Si encontramos un texto válido, usarlo
                if mejor:
                    row = mejor['texto']
                    
                    nearest_texts.append({'Symbol_Location': sym['Symbol_Location'],'Symbol_Name': sym.get('Name_key'),'Data_Link': sym.get('Data_Link', ''),
                                          'Text_Name': row.get('Name_Key', ''),'Text_Location': row.get('Symbol_Location', ''),'Name Unifilar': nivel})
                else:
                    # Si no hay textos válidos (sin espacios y ≤10 caracteres), añadir a sin texto
                    sym_copy = sym.copy(); sym_copy['Name Unifilar'] = nivel
                    sin_texto.append(sym_copy)
            else:
                sym_copy = sym.copy(); sym_copy['Name Unifilar'] = nivel
                sin_texto.append(sym_copy)
        nearest_texts_dict[nivel] = pd.DataFrame(nearest_texts)
    all_objects = pd.concat(nearest_texts_dict.values(), ignore_index=True) if nearest_texts_dict else pd.DataFrame()
    sin_data_link_df = pd.concat(sin_data_link.values(), ignore_index=True) if sin_data_link else pd.DataFrame()
    sin_data_link_df = sin_data_link_df.drop(columns=['Name_Key','Tipo'], errors='ignore')
    sin_texto_df = pd.concat(sin_texto, axis=1).T if sin_texto else pd.DataFrame()
    filtered_all = all_objects[all_objects.apply(lambda r: r['Text_Name'] not in str(r['Symbol_Name']), axis=1)] if not all_objects.empty else pd.DataFrame()
    if not filtered_all.empty: filtered_all = filtered_all.copy(); filtered_all['Estado'] = 'Texto no coincide con símbolo'
    if not sin_data_link_df.empty: sin_data_link_df['Estado'] = 'Sin Data Link'
    if not all_objects.empty: all_objects['Estado'] = 'Texto más cercano asignado'
    if not sin_texto_df.empty: sin_texto_df['Estado'] = 'Sin texto cercano'
    
    # Renombrar columnas y eliminar las no deseadas
    columns_to_drop = ['Text_Location', 'Symbol Key', 'Tipo', 'Name Key', 'Name_Key', 'X', 'Y']
    
    for df in [filtered_all, sin_data_link_df, all_objects, sin_texto_df]:
        if not df.empty:
            df = df.copy()
            df.drop(columns=[col for col in columns_to_drop if col in df.columns], inplace=True)
    return filtered_all, sin_data_link_df, all_objects, sin_texto_df

def filtrar_textos_unidad(unifilar, SCADA_SIGNAL, name_unifilar=None):
    # Extraer datos con Name_Key para procesamiento interno
    objetos = unifilar.get('ObjectList', {})
    data = []
    for key, value in objetos.items():
        tipo = value.get('Type')
        if tipo != 'TextObject':
            continue
        keys = extraer_keys(value)
        data_key = keys.get('data_key')
        entry = {
            'ID': key, 'Symbol_Location': None, 'Data_Link': data_key,
            'Symbol Key': value.get('Symbol Key'), 'Tipo': tipo, 'Name_Key': None
        }
        if loc := value.get('Location'):
            coords = [p.strip() for p in loc.strip('() ').split(',')]
            if len(coords) >= 2:
                entry['Symbol_Location'] = f"( {coords[0]}, {coords[1]} )"
        entry['Name_Key'] = value.get('String') or value.get('Format String')
        data.append(entry)
    
    df_text_units = pd.DataFrame(data)
    if df_text_units.empty:
        return pd.DataFrame()
    
    # Filtrar y procesar
    df_text_units = df_text_units[df_text_units['Data_Link'].notna() & (df_text_units['Data_Link'] != '')]
    df_text_units = df_text_units[df_text_units['Data_Link'].astype(str).str.len() == 8]
    df_en_scada = pd.merge(df_text_units, SCADA_SIGNAL[['Key', 'pUNIT']], left_on='Data_Link', right_on='Key', how='left')
    df_en_scada['pUNIT'] = df_en_scada['pUNIT'].fillna('').str.strip()
    df_en_scada['Name_Key'] = df_en_scada['Name_Key'].fillna('')
    df_en_scada_filtrado = df_en_scada[~df_en_scada.apply(lambda fila: fila['pUNIT'] in fila['Name_Key'], axis=1)]
    df_en_scada_filtrado = df_en_scada_filtrado.copy()
    df_en_scada_filtrado['Estado'] = 'Texto no contiene unidad'
    
    # Agregar Name Unifilar
    if name_unifilar:
        df_en_scada_filtrado['Name Unifilar'] = name_unifilar
    
    # Renombrar Name_Key a Text_Name y eliminar columnas no deseadas
    df_en_scada_filtrado = df_en_scada_filtrado.drop(columns=['Tipo', 'Key'], errors='ignore')
    df_en_scada_filtrado = df_en_scada_filtrado.rename(columns={
        'Name_Key': 'Text_Name', 'pUNIT':'Text_Scada'
    })
    
    # Eliminar todas las columnas no deseadas incluyendo Symbol Key
    columns_to_drop = ['Symbol Key', 'Name Key', 'X', 'Y']
    df_en_scada_filtrado = df_en_scada_filtrado.drop(columns=[col for col in columns_to_drop if col in df_en_scada_filtrado.columns])
    
    return df_en_scada_filtrado

def limpiar_dataframe_final(df):
    """Limpia el DataFrame final eliminando columnas no deseadas"""
    if df.empty:
        return df
    
    # Eliminar TODAS las variantes de columnas no deseadas
    columns_to_drop = ['Text_Location', 'Symbol Key', 'Tipo', 'Name Key', 'Name_Key', 'X', 'Y', 'Name_key', 'ID']
    df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])
    
    return df

# =====================
# ANÁLISIS PRINCIPAL Y EXPORTACIÓN DE REPORTES 
# =====================
def run_validaciones_unifilar(archivos_unifilar, output_dir, logger_in, SCADA_DIR):
    global logger, logger_console
    logger = logger_in

    if isinstance(archivos_unifilar, str):
        archivos_unifilar = [archivos_unifilar]
    reportes_keys, reportes_finales, errores = [], [], []

    # Constante para el filtro post-validación
    EXCLUDED_SYMBOL_KEY = 'SELECTORES Y EQUIPOS ESPECIALES.LIB2 24'

    for archivo_unifilar in archivos_unifilar:
        try:
            Logger.write_log().log_all('info', f'Procesando archivo unifilar: {archivo_unifilar}', logger_console, logger)
            data = leer_archivo(archivo_unifilar)
            SCADA_SIGNAL, opennet_status = cargar_datos_scada(SCADA_DIR)
            
            # Extraer el name_unifilar del DisplayName
            nombre_display = data.get('DisplayName', [''])[0]
            name_unifilar = re.split(r'[_\.]', nombre_display)[0] if nombre_display else os.path.splitext(os.path.basename(archivo_unifilar))[0]
            
            resultados = analizar_objetos(data, os.path.basename(archivo_unifilar), opennet_status)
            Logger.write_log().log_all('info', 'Construyendo DataFrame de claves...', logger_console, logger)
            df_keys = pd.DataFrame(resultados)

            if not df_keys.empty and 'Key_Status' in df_keys.columns:
                df_diferentes = df_keys[df_keys['Key_Status'] == 'Keys diferentes']
                scada_keys = set(SCADA_SIGNAL['Key'].astype(str))
                df_faltantes = df_keys[~df_keys['Key'].isin(scada_keys)].copy()
                df_faltantes['Key_Status'] = 'No existe en SCADA'
                reporte = pd.concat([df_diferentes, df_faltantes])
                
                # APLICAR FILTRO POST-VALIDACIÓN solo a "Keys diferentes"
                if not reporte.empty:
                    # Crear máscara para excluir señales 41 específicas SOLO de "Keys diferentes"
                    mask_excluir = (
                        (reporte['Key_Status'] == 'Keys diferentes') &
                        (reporte['Symbol_Key'] == EXCLUDED_SYMBOL_KEY) &
                        (reporte['Key_data_link'].astype(str).str.startswith('41')) &
                        (reporte['Key_color_link'].astype(str).str.startswith(('01', '22')))
                    )
                    
                    # Aplicar filtro - excluir solo las que cumplen todas las condiciones
                    reporte = reporte[~mask_excluir]
                
                reporte = reporte.sort_values(['File_Name', 'Key'])
                if not reporte.empty:
                    reportes_keys.append(reporte)

            df_pages = build_display_dataframe(data)
            df_symbols_and_text_analog = extract_data(data, 'SymbolRefObject', solo_symbol=False)
            results = group_by_level(df_pages, df_symbols_and_text_analog)
            df_diferente_station = pstation_review(results, SCADA_SIGNAL)

            df_text = extract_data(data, 'TextObject', solo_symbol=False, capa1=True)
            df_only_symbols = extract_data(data, 'SymbolRefObject', solo_symbol=True)
            df_only_symbols = add_scada_name(df_only_symbols, SCADA_SIGNAL)
            all_objs = pd.concat([df_only_symbols, df_text], ignore_index=True)
            results2 = group_by_level(df_pages, all_objs)

            symbol_keys_filtrar = [
                'EQUIPOS_DE_MANIOBRA.LIB2 1', 'EQUIPOS_DE_MANIOBRA.LIB2 2', 'EQUIPOS_DE_MANIOBRA.LIB2 3',
                'EQUIPOS_DE_MANIOBRA.LIB2 6', 'EQUIPOS_DE_MANIOBRA.LIB2 10', 'EQUIPOS_DE_MANIOBRA.LIB2 11',
                'EQUIPOS_DE_MANIOBRA.LIB2 12', 'EQUIPOS_DE_MANIOBRA.LIB2 14']
            symbols_with_text, sin_data_link, _, sin_text = analizar_proximidad(results2, symbol_keys_filtrar)

            # Pasar name_unifilar a la función
            df_en_scada_filtrado = filtrar_textos_unidad(data, SCADA_SIGNAL, name_unifilar)

            for df in [df_diferente_station, symbols_with_text, sin_data_link, sin_text, df_en_scada_filtrado]:
                if not df.empty and 'Estado' in df.columns:
                    df = df.copy()
                    df['File_Name'] = os.path.basename(archivo_unifilar)

            resultados_finales = [df for df in [df_diferente_station, symbols_with_text, sin_data_link, sin_text, df_en_scada_filtrado]
                                  if not df.empty and 'Estado' in df.columns]
            if resultados_finales:
                df_concatenado = pd.concat(resultados_finales, ignore_index=True)
                reportes_finales.append(df_concatenado)

            Logger.write_log().log_all('info', f'Fin de la validación para {archivo_unifilar}', logger_console, logger)
        except Exception as e:
            Logger.write_log().log_all('error', f"No se pudo validar el archivo {archivo_unifilar}: {e}", logger_console, logger)
            errores.append((archivo_unifilar, str(e)))

    os.makedirs(output_dir, exist_ok=True)
    
    # Generar timestamp para los nombres de archivos
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if reportes_keys:
        df_keys_total = pd.concat(reportes_keys, ignore_index=True)
        path_excel_keys = os.path.join(output_dir, f'Report_unifilares_keys_{timestamp}.xlsx')
        df_keys_total.to_excel(path_excel_keys, index=False)
        aplicar_formato_excel(path_excel_keys)
        Logger.write_log().log_all('info', f"Reporte global de claves guardado en: {path_excel_keys}", logger_console, logger)
    if reportes_finales:
        df_final_total = pd.concat(reportes_finales, ignore_index=True)
        # Aplicar limpieza final al DataFrame
        df_final_total = limpiar_dataframe_final(df_final_total)
        path_excel_final = os.path.join(output_dir, f'Report_unifilares_final_{timestamp}.xlsx')
        df_final_total.to_excel(path_excel_final, index=False)
        aplicar_formato_excel(path_excel_final)
        Logger.write_log().log_all('info', f"Reporte global final guardado en: {path_excel_final}", logger_console, logger)
    if errores:
        Logger.write_log().log_all('warning', 'Archivos que no se pudieron validar:', logger_console, logger)
        for archivo, err in errores:
            Logger.write_log().log_all('warning', f"- {archivo}: {err}", logger_console, logger)
    if not reportes_keys and not reportes_finales and not errores:
        Logger.write_log().log_all('warning', 'No hay resultados para mostrar.', logger_console, logger)

    total_archivos = len(archivos_unifilar)
    total_errores = len(errores)
    total_ok = total_archivos - total_errores
    resumen = (
        f"\nResumen de procesamiento:\n"
        f"  Archivos solicitados: {total_archivos}\n"
        f"  Procesados correctamente: {total_ok}\n"
        f"  Con error: {total_errores}\n"
    )
    Logger.write_log().log_all('info', resumen, logger_console, logger)
    return resumen

def main():
    global logger, logger_console
    parser = argparse.ArgumentParser(description="Validación de Unifilares desde interfaz")
    parser.add_argument('--archivos', nargs='+', required=True, help='Archivos unifilares a validar')
    parser.add_argument('--empresa', required=True, help='Nombre de la empresa (para leer SCADA en out/<empresa>/SCADA)')
    args = parser.parse_args()

    log_dir = os.path.join(_rt(), 'log')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'validacion_unifilares.log')
    logger, logger_console = Logger.initlog(log_path)

    BASE_DIR = get_base_dir(args.empresa)
    SCADA_DIR = os.path.join(BASE_DIR, 'SCADA')
    out_dir = os.path.join(_rt(), "out", "Validacion_Unifilares")

    resumen = run_validaciones_unifilar(args.archivos, out_dir, logger, SCADA_DIR)
    print(resumen)

if __name__ == "__main__":
    main()
