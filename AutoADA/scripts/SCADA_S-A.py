import pandas as pd
import csv
import os
import sys
import argparse
import uuid
import unicodedata
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from copy import copy
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

def get_resource_path(relative_path):
    """Obtiene la ruta correcta del recurso en ejecutable y desarrollo"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def _runtime_root() -> str:
    """Raíz de trabajo (lectura/escritura) -> carpeta donde corre el exe."""
    return os.getcwd()

base_dir = _runtime_root()

def _scada_path(root: str, empresa: str, dominio: str | None = None) -> str:
    """Ruta a SCADA según dominio (default SCADA)."""
    suffix = f"{dominio}SCADA" if dominio else "SCADA"
    return os.path.join(root, "out", empresa, suffix)

# Inicialización del logger personalizado
log_dir = os.path.join(base_dir, 'log')
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, 'Scada_load.log')
logger, logger_console = Logger.initlog(log_path, append=True)  

def get_args():
    parser = argparse.ArgumentParser(description='Script para dividir las senales en cada tipo')
    parser.add_argument('empresa', type=str, help='Nombre de la empresa')
    parser.add_argument('--dominio', type=str, default=None, help='Dominio (ej: CC, QA) para segmentar rutas SCADA')
    return parser.parse_args()

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
    
    # Aplicar normalización a todas las columnas de tipo object (string)
    for columna in df_normalizado.columns:
        try:
            if df_normalizado[columna].dtype == 'object':
                df_normalizado[columna] = df_normalizado[columna].apply(normalizar_texto_sin_tildes)
        except Exception as e:
            # Si hay error con una columna específica, continuar con las demás
            Logger.write_log().log_all('warning', f"Error normalizando columna '{columna}': {e}", logger_console, logger)
            continue
    
    return df_normalizado

def procesar_datos():
    try:
        Logger.write_log().log_all('info', 'Inicia asignacion SCADA FEP ICCP', logger_console, logger)

        # Leer todas las hojas del archivo Excel
        excel_path = os.path.join(base_dir, 'out', 'Load', 'Señales_with_keys.xlsx')
        dfs = pd.read_excel(excel_path, sheet_name=None, header=0, dtype={'Scada Key': str})
        Logger.write_log().log_all('info', 'Archivo Excel cargado', logger_console, logger)

        # Normalizar texto removiendo tildes en todas las hojas
        for sheet_name, df in dfs.items():
            if not df.empty:
                # Normalizar nombres de columnas
                df.columns = [normalizar_texto_sin_tildes(str(col)) if pd.notna(col) else col for col in df.columns]
                # Normalizar contenido
                dfs[sheet_name] = normalizar_dataframe(df)
        Logger.write_log().log_all('info', 'Texto normalizado (tildes removidas)', logger_console, logger)

        # Verificar si las hojas existen y procesarlas
        status_df = dfs.get('STATUS', pd.DataFrame())
        control_fep = status_df.copy()
        analog_df = dfs.get('ANALOG', pd.DataFrame())
        
        status_df_checklist = status_df.copy()
        analog_df_checklist = analog_df.copy()

        # Carpeta de salida (Load)
        carpeta = os.path.join(base_dir, 'out', 'Load')
        os.makedirs(carpeta, exist_ok=True)

        args = get_args()
        empresa = args.empresa
        ruta_scada = _scada_path(base_dir, empresa, args.dominio)
        Logger.write_log().log_all('info', 'Carpeta Load lista', logger_console, logger)

        # === FUNCIONES AUXILIARES ===
        def evaluar_tipo(row):
            return {"T_IND": 1, "T_I&C": 2, "T_CTL": 3, "T_ALM":4,"C_IND":5 ,"T_R/L": 6,"T_JOG": 7,"M_IND": 8,"G_CTL": 9}.get(row['Type'], 0)

        def analog_logic(row):
            if row['Name'] != 0:
                return {"T_ANLG": 1, "C_ANLG": 2}.get(row['Type'], 'ERROR')
            return None

        def extraer_subcadena(valor):
            return None if pd.isna(valor) else valor.split(':')[0]

        # ---------------- STATUS ----------------
        if not status_df.empty:
            status_df.insert(0, '4', None)
            status_df.insert(1, 'STATUS', None)
            # Asignar secuencia descendente de negativos: -1, -2, -3, ...
            status_df.insert(2, 'record', list(range(-1, -len(status_df) - 1, -1)))
            status_df.insert(3, 'OrderNo', range(1, len(status_df) + 1))
            status_df['Type'] = status_df.apply(evaluar_tipo, axis=1)
            status_df['pStation'] = status_df['Station'].apply(extraer_subcadena)
            status_df['pALARM_GROUP'] = status_df['Alarm Group'].apply(extraer_subcadena)
            status_df['pConfiguredAORGroup'] = status_df['AOR Group'].apply(extraer_subcadena)
            status_df['pCtrlState'] = status_df['State Table for Controls'].apply(extraer_subcadena).fillna(0)
            status_df['pStates'] = status_df['State Table'].str.slice(0, 3)

            column_order = [
                '4','STATUS','record','OrderNo','Type','Scada Key','Name','pStation','pStates',
                'pALARM_GROUP','pConfiguredAORGroup','pCtrlState','Normal State','Quad','Single Trip','Timer ']
            
            status_df = status_df[column_order]
            status_df = status_df.rename(columns={
                'Scada Key': 'Key','Normal State':'ConfigNormalState',
                'Quad':'ConfigBits','Single Trip':'ConfigBits2','Timer ':'Timer'
            })
            status_df['ConfigBits'] = status_df['ConfigBits'].replace(1, 8)
            status_df['ConfigBits2'] = status_df['ConfigBits2'].replace(1, 16)
            # Convertir Timer a entero para evitar decimales en CSV
            if 'Timer' in status_df.columns:
                status_df['Timer'] = pd.to_numeric(status_df['Timer'], errors='coerce').fillna(0).astype(int)
            
            # Convertir ConfigNormalState a entero si existe
            if 'ConfigNormalState' in status_df.columns:
                status_df['ConfigNormalState'] = pd.to_numeric(status_df['ConfigNormalState'], errors='coerce').fillna(0).astype(int)
            Logger.write_log().log_all('info', f'STATUS procesado: {len(status_df)} registros', logger_console, logger)
        else:
            Logger.write_log().log_all('warning', 'Hoja STATUS vacía, se omitirá', logger_console, logger)

        # ---------------- ANALOG ----------------
        if not analog_df.empty:
            analog_df.insert(0, '5', None)
            analog_df.insert(1, 'ANALOG', None)
            # Asignar secuencia descendente de negativos: -1, -2, -3, ...
            analog_df.insert(2, 'record', list(range(-1, -len(analog_df) - 1, -1)))
            analog_df.insert(3, 'OrderNo', range(1, len(analog_df) + 1))
            analog_df['Type'] = analog_df.apply(analog_logic, axis=1)
            analog_df['pStation'] = analog_df['Station'].apply(extraer_subcadena)
            analog_df['pUNIT'] = analog_df['Units'].apply(extraer_subcadena)
            analog_df['pScale'] = analog_df['Scale Factor'].apply(extraer_subcadena)
            analog_df['pALARM_GROUP'] = analog_df['Alarm Group'].apply(extraer_subcadena)
            analog_df['RawCountFormat'] = analog_df['Name'].apply(lambda x: 5 if x != 0 else None)
            analog_df['pConfiguredAORGroup'] = analog_df['AOR Group'].apply(extraer_subcadena)

            analog_df = analog_df.rename(columns={
                'Scada Key':'Key','H Lim 1':'NominalHiLimits;0','H Lim 2':'NominalHiLimits;1',
                'H Lim 3':'NominalHiLimits;2','H Lim 4':'NominalHiLimits;3','H Lim Rsn':'NominalHiLimits;4',
                'L Lim 1':'NominalLowLimits;0','L Lim 2':'NominalLowLimits;1','L Lim 3':'NominalLowLimits;2',
                'L Lim 4':'NominalLowLimits;3','L Lim Rsn':'NominalLowLimits;4',
                'Active Lim':'NominalPairInactive','Flatline time (s)':'Flatline_time'
            })

            columns_to_fill = ['4 seg ins','1 min ins','5 min ins','5 min avg','1 hor avg','1 hor max','1 hor min','HRS']
            analog_df[columns_to_fill] = analog_df[columns_to_fill].fillna(0).astype(int)
            analog_df['Archive_group'] = sum(analog_df[col]*(2**i) for i,col in enumerate(columns_to_fill))
            analog_df['Archive_group2'] = analog_df.apply(lambda row: "¡Revisar 1min!" if row['1 min ins']==1 else row['15 min ins']*1, axis=1)
            analog_df['Archive_group2'] = analog_df['Archive_group2'].fillna(0).astype(int)

            ordered_columns = [
                '5','ANALOG','record','OrderNo','Type','Key','Name','pStation','pUNIT','pScale',
                'pALARM_GROUP','RawCountFormat','pConfiguredAORGroup',
                'NominalHiLimits;0','NominalHiLimits;1','NominalHiLimits;2',
                'NominalHiLimits;3','NominalHiLimits;4',
                'NominalLowLimits;0','NominalLowLimits;1','NominalLowLimits;2',
                'NominalLowLimits;3','NominalLowLimits;4',
                'NominalPairInactive','Flatline_time','Archive_group','Archive_group2'
            ]
            analog_df = analog_df[ordered_columns]
            Logger.write_log().log_all('info', f'ANALOG procesado: {len(analog_df)} registros', logger_console, logger)
        else:
            Logger.write_log().log_all('warning', 'Hoja ANALOG vacía, se omitirá', logger_console, logger)

        # ---------------- CONTROLS_FEP ----------------
        if not control_fep.empty and 'Command Type' in control_fep.columns:
            control_fep1 = control_fep[control_fep['Command Type'].isin(['DC','SC','RC'])].copy()
            
            if not control_fep1.empty:
                # Crear columnas nuevas
                control_fep1['20'] = None
                control_fep1['RTU_CONTROL'] = None
                # Asignar secuencia descendente de negativos: -1, -2, -3, ...
                control_fep1['record'] = list(range(-1, -len(control_fep1) - 1, -1))
                control_fep1['Indic'] = 1
                control_fep1['SourceKey'] = control_fep1['Scada Key']
                control_fep1['control_type'] = control_fep1['Command Type'].map({'RC': 3, 'SC': 5, 'DC': 6})
                control_fep1['point_address'] = pd.to_numeric(control_fep1['Command Address'], errors='coerce').fillna(0).astype(int)
                control_fep1['pRTU'] = control_fep1['RTU'].apply(extraer_subcadena)
                control_fep1['proto_parms;0'] = control_fep1['SourceKey'].notna().astype(int)
                control_fep1['proto_parms;1'] = control_fep1['Command Type'].apply(lambda x: 1 if x == 'DC' else 0)

                # Agregar proto_parms;2 a proto_parms;7 con valor 0
                for i in range(2, 8):
                    control_fep1[f'proto_parms;{i}'] = 0

                control_fep1['control_format'] = 2
                control_fep1['SourceObject'] = 4

                # Reordenar columnas
                column_order = [
                    '20', 'RTU_CONTROL', 'record', 'Indic', 'SourceKey', 'control_type',
                    'point_address', 'pRTU', 'proto_parms;0', 'proto_parms;1',
                    'proto_parms;2', 'proto_parms;3', 'proto_parms;4', 'proto_parms;5',
                    'proto_parms;6', 'proto_parms;7', 'control_format', 'SourceObject'
                ]

                # Asegurarse de que todas las columnas estén presentes
                control_fep1 = control_fep1[column_order]

                # Formatear SourceKey con comillas
                control_fep1['SourceKey'] = control_fep1['SourceKey'].apply(lambda x: f'"{x}"' if pd.notna(x) else '""')
                Logger.write_log().log_all('info', f'CONTROLS_FEP procesado: {len(control_fep1)} registros', logger_console, logger)
            else:
                control_fep1 = pd.DataFrame()
                Logger.write_log().log_all('info', 'No hay comandos (DC/SC/RC) en STATUS', logger_console, logger)
        else:
            control_fep1 = pd.DataFrame()
            Logger.write_log().log_all('warning', 'No se puede procesar CONTROLS_FEP (STATUS vacío o sin Command Type)', logger_console, logger)
#---------------------------------Scan Data----------------------------------------------
        scan_data_path = os.path.join(carpeta,'scan_data.csv')
        # Leer y procesar el archivo 32_10 para usar claves que existen en fep pero no tienen destination_key
        df_32_10 = pd.read_csv(os.path.join(ruta_scada, '32_10.csv'),usecols=['#record','Key', 'DestinationKey','GuidAsString'],
            encoding='ISO-8859-1',low_memory=False)
        # Filtrar filas donde DestinationKey esté vacío o nulo
        df_32_10 = df_32_10[df_32_10['DestinationKey'].isna() |(df_32_10['DestinationKey'].astype(str).str.strip() == '')]
        # Filtrar filas donde Key comience por '01', '02', '03' o '04'
        df_32_10 = df_32_10[ df_32_10['Key'].astype(str).str.startswith(('01', '02', '03', '04'))]
        # Crear el diccionario Key -> Guid
        diccionario_key_guid = dict(zip(df_32_10['Key'].astype(str), df_32_10['GuidAsString'].astype(str)))
        diccionario_key_record = dict(zip(df_32_10['Key'].astype(str), df_32_10['#record'].astype(int)))
        
        nuevos_counts_path = os.path.join(carpeta,'Nuevos_counts.csv')
        if os.path.exists(scan_data_path):
            scan_data_df = pd.read_csv(scan_data_path, encoding='utf-8', low_memory=False, dtype={'Key':str,'DestinationKey':str,'Name':str,'point_address':int})
            scan_data_df['GuidAsString'] = scan_data_df['Key'].astype(str).map(diccionario_key_guid)
            scan_data_df['#Record'] = scan_data_df['Key'].astype(str).map(diccionario_key_record).fillna(scan_data_df['#Record'])
            # Renumerar negativos a secuencia -1, -2, -3 tras aplicar mapeo a records existentes
            _rec_numeric = pd.to_numeric(scan_data_df['#Record'], errors='coerce')
            _neg_mask = _rec_numeric < 0
            if _neg_mask.any():
                scan_data_df.loc[_neg_mask, '#Record'] = list(range(-1, -_neg_mask.sum() - 1, -1))
            for col in ['Key','DestinationKey','Name']:
                scan_data_df[col] = scan_data_df[col].apply(lambda x: f'"{x}"' if pd.notna(x) and x!='' else x)
            os.remove(scan_data_path)
        else:
            scan_data_df=None
        if os.path.exists(nuevos_counts_path):
            nuevos_counts_df=pd.read_csv(nuevos_counts_path,encoding='utf-8',low_memory=False)
            os.remove(nuevos_counts_path)
        else:
            nuevos_counts_df=None
        
        def assign_unique_guids(scan_data_df, controls_fep, carpeta_scada):
            # Leer GUIDs existentes de los archivos CSV
            guids = set()
            for fname in ["32_10.csv", "32_20.csv"]:
                fpath = os.path.join(carpeta_scada, fname)
                if os.path.exists(fpath):
                    df = pd.read_csv(fpath, dtype=str)
                    if 'GuidAsString' in df.columns:
                        guids.update(df['GuidAsString'].dropna().unique())
            
            def fill_guids(df):
                # Manejar caso donde df es None
                if df is None:
                    return None
                df = df.copy()
                if 'GuidAsString' not in df.columns:
                    df['GuidAsString'] = None
                mask = df['GuidAsString'].isna() | (df['GuidAsString'] == '') | (df['GuidAsString'] == 'None')
                needed = mask.sum()
                new_guids = []
                while len(new_guids) < needed:
                    guid = str(uuid.uuid4())
                    if guid not in guids:
                        new_guids.append(guid)
                        guids.add(guid)
                df.loc[mask, 'GuidAsString'] = new_guids
                return df

            scan_data_df = fill_guids(scan_data_df)
            if scan_data_df is not None:
                scan_data_df['#Record'] = scan_data_df['#Record'].astype(int)
            controls_fep = fill_guids(controls_fep)
            return scan_data_df, controls_fep

        scan_data_df, control_fep1 = assign_unique_guids(scan_data_df, control_fep1, ruta_scada)
        def guardar_scada(df1,df2,path):
            if (df1 is None or df1.empty) and (df2 is None or df2.empty):
                Logger.write_log().log_all('warning', "DataFrames vacios, SCADA no se guarda", logger_console, logger)
                return
            with open(path,'w',newline='') as f:
                f.write("10,SCADA.DB\n")
                if df1 is not None and not df1.empty:
                    df1.to_csv(f,index=False,quoting=csv.QUOTE_NONE)
                    f.write("0\n")
                if df2 is not None and not df2.empty:
                    if df1 is not None and not df1.empty:
                        f.write("*\n")
                    df2.to_csv(f,index=False,quoting=csv.QUOTE_NONE)
                    f.write("0\n")
                f.write("0")
            Logger.write_log().log_all('info',f"Archivo SCADA guardado: {path}",logger_console,logger)

        guardar_scada(status_df, analog_df, os.path.join(carpeta,'10_SCADA.csv'))

        def guardar_fep(scan_df,counts_df,controls_df,path):
            bloques=[]
            if scan_df is not None and not scan_df.empty: bloques.append(scan_df)
            if counts_df is not None and not counts_df.empty: bloques.append(counts_df)
            if controls_df is not None and not controls_df.empty: bloques.append(controls_df)
            if not bloques:
                Logger.write_log().log_all('warning',"DataFrames vacios, FEP no se guarda.",logger_console,logger)
                return
            with open(path,'w',newline='') as f:
                f.write("32,FEP.DB\n")
                for i,bloque in enumerate(bloques):
                    bloque.to_csv(f,index=False,quoting=csv.QUOTE_NONE)
                    f.write("0\n")
                    if i<len(bloques)-1:
                        f.write("*\n")
                f.write("0")
            Logger.write_log().log_all('info',f"Archivo FEP guardado: {path}",logger_console,logger)
        
        guardar_fep(scan_data_df, nuevos_counts_df, control_fep1, os.path.join(carpeta,'32_FEP.csv'))
        
        def asignar_iccp(dfs):
            # Cargar datos base
            df_36_16 = pd.read_csv(os.path.join(ruta_scada, '36_16.csv'), encoding='utf-8', low_memory=False, dtype={'Name':'str'})
            diccionario_nombre_record = dict(zip(df_36_16['Name'], df_36_16['#record']))
            
            # Preparar datos ICCP combinados
            combined_iccp = pd.concat([
                df[df['Import ICCP Name'].notna()].assign(Tipo=tipo)[['Import ICCP Name', 'Scada Key', 'Tipo']]
                for (sheet, tipo) in [('STATUS', '4'), ('ANALOG', '5')]
                if not (df := dfs.get(sheet, pd.DataFrame())).empty
            ], ignore_index=True)
            
            if combined_iccp.empty:
                return pd.DataFrame(), pd.DataFrame()
            
            # Separar existentes y nuevas
            mask = combined_iccp['Import ICCP Name'].isin(diccionario_nombre_record.keys())
            existentes_temp, nuevas_temp = combined_iccp[mask].copy(), combined_iccp[~mask].copy()
            
            # Procesar existentes - Crear DataFrame completamente nuevo
            existentes = pd.DataFrame()
            if not existentes_temp.empty:
                # Mapear records y asignar secuencia negativa para los que no tengan record
                _map_records = existentes_temp['Import ICCP Name'].map(diccionario_nombre_record)
                _missing_mask = _map_records.isna()
                if _missing_mask.any():
                    _seq = list(range(-1, -_missing_mask.sum() - 1, -1))
                    _map_records.loc[_missing_mask] = _seq
                existentes = pd.DataFrame({
                    '16': [None]*len(existentes_temp),
                    'ICCP_IMPORT_POINT': [None]*len(existentes_temp),
                    '#Record': _map_records.astype(int),
                    'Indic': range(1, len(existentes_temp) + 1),
                    'REC_KEY': existentes_temp['Scada Key'].values
                })
            
            # Procesar nuevas - Crear DataFrame completamente nuevo
            df_nuevas = pd.DataFrame()
            if not nuevas_temp.empty and not (df_iccp := dfs.get('ICCP', pd.DataFrame())).empty:
                lookup = df_iccp.set_index('Name')[['Type', 'plmpsDS']].to_dict('index')
                
                df_nuevas = pd.DataFrame({
                    '16': [None]*len(nuevas_temp),
                    'ICCP_IMPORT_POINT': [None]*len(nuevas_temp),
                    '#Record': list(range(-1, -len(nuevas_temp) - 1, -1)),
                    'Indic': range(1, len(nuevas_temp) + 1),
                    'DB_NUM': [10]*len(nuevas_temp),
                    'OBJ_NUM': nuevas_temp['Tipo'].values,
                    'FIELD_NUM': [20]*len(nuevas_temp),
                    'INDEX_NUM': [0]*len(nuevas_temp),
                    'REC_KEY': nuevas_temp['Scada Key'].values,
                    'TYPE': [str(lookup.get(x, {}).get('Type', '')).split(':')[0] if ':' in str(lookup.get(x, {}).get('Type', '')) else lookup.get(x, {}).get('Type') for x in nuevas_temp['Import ICCP Name']],
                    'pImpDS': [str(lookup.get(x, {}).get('plmpsDS', '')).split(':')[0] if ':' in str(lookup.get(x, {}).get('plmpsDS', '')) else None for x in nuevas_temp['Import ICCP Name']],
                    'Name': nuevas_temp['Import ICCP Name'].values
                })
            elif not nuevas_temp.empty:
                Logger.write_log().log_all('warning', 'No se puede crear senales ICCP sin hoja ICCP', logger_console, logger)
            
            Logger.write_log().log_all('info', f'Senales ICCP existentes: {len(existentes)}, nuevas: {len(df_nuevas)}', logger_console, logger)
            return existentes, df_nuevas
        # Función para guardar ICCP
        def guardar_iccp(df_existentes_iccp, df_nuevas_iccp, path):
            bloques = []
            if df_existentes_iccp is not None and not df_existentes_iccp.empty: 
                bloques.append(df_existentes_iccp)
            if df_nuevas_iccp is not None and not df_nuevas_iccp.empty: 
                bloques.append(df_nuevas_iccp)
            
            if not bloques:
                Logger.write_log().log_all('warning', "DataFrames vacios, ICCP no se guarda.", logger_console, logger)
                return
            
            with open(path, 'w', newline='') as f:
                f.write("36,ICCP.DB\n")
                for i, bloque in enumerate(bloques):
                    bloque.to_csv(f, index=False, quoting=csv.QUOTE_NONE)
                    f.write("0\n")
                    if i < len(bloques) - 1:
                        f.write("*\n")
                f.write("0")
            
            Logger.write_log().log_all('info', f"Archivo ICCP guardado: {path}", logger_console, logger)

        # Agregar después de la función asignar_iccp:
        existentes_iccp, nuevas_iccp = asignar_iccp(dfs)
        guardar_iccp(existentes_iccp, nuevas_iccp, os.path.join(carpeta, '36_ICCP.csv'))
            
        def guardar_checklist(status_df_checklist, analog_df_checklist):
            checklist_path_read = get_resource_path("templates/Checklist_V1.xlsx")
            checklist_path_save = os.path.join(carpeta, 'Checklist_scada_load.xlsx')
            
            try:
                # Verificar si ambos DataFrames están vacíos
                if status_df_checklist.empty and analog_df_checklist.empty:
                    Logger.write_log().log_all('warning', 'No hay datos para generar Checklist (STATUS y ANALOG vacíos)', logger_console, logger)
                    return
                
                # Configurar datos optimizado
                cols = ['Command Address','Monitoring Address','Scada Key','AOR Group','Type','Station','Name']
                rename_map = {'Monitoring Address':'IOA','Command Address':'IOA','Scada Key':'Scada Key','AOR Group':'AOR','Type':'type'}
                
                # Preparar DataFrames por hoja con manejo de vacíos
                sheets_data = {}
                
                if not status_df_checklist.empty:
                    # Verificar que las columnas necesarias existan
                    cols_disponibles = [c for c in cols if c in status_df_checklist.columns]
                    if cols_disponibles:
                        status_filt = status_df_checklist[cols_disponibles]
                        
                        # STATUS sheet
                        if 'Type' in status_filt.columns:
                            status_sheet = status_filt[status_filt['Type'].isin(['T_IND','T_I&C','M_IND','C_IND'])]
                            if 'Command Address' in status_sheet.columns:
                                status_sheet = status_sheet.drop(columns=['Command Address'])
                            sheets_data['STATUS'] = status_sheet.rename(columns=rename_map)
                        
                        # CMD sheet
                        if 'Type' in status_filt.columns:
                            cmd_sheet = status_filt[status_filt['Type'].isin(['T_I&C','T_CTL','T_R/L'])]
                            cols_drop = [c for c in ['Monitoring Address','AOR Group','Station'] if c in cmd_sheet.columns]
                            if cols_drop:
                                cmd_sheet = cmd_sheet.drop(columns=cols_drop)
                            sheets_data['CMD'] = cmd_sheet.rename(columns=rename_map)
                
                # ANALOG sheet
                if not analog_df_checklist.empty:
                    analog_cols = ['Monitoring Address','Scada Key','AOR Group','Type','Station','Name']
                    analog_cols_disponibles = [c for c in analog_cols if c in analog_df_checklist.columns]
                    if analog_cols_disponibles:
                        sheets_data['ANALOG'] = analog_df_checklist[analog_cols_disponibles].rename(columns=rename_map)
                
                wb = load_workbook(checklist_path_read, keep_links=False, data_only=False)
                
                for sheet_name, df in sheets_data.items():
                    if sheet_name in wb.sheetnames and not df.empty:
                        ws = wb[sheet_name]
                        #Agregar filtros y congelar encabezado
                        ws.auto_filter.ref = ws.dimensions
                        ws.freeze_panes = "A2"
                        # Capturar formato de la fila 1 (encabezados) para usar como plantilla
                        header_styles = {}
                        for col_idx in range(1, ws.max_column + 1):
                            header_cell = ws.cell(2, col_idx)
                            # Crear una fuente sin negrilla para los datos
                            data_font = copy(header_cell.font)
                            data_font.bold = False  # Remover la negrilla
                            
                            header_styles[col_idx] = {
                                'fill': copy(header_cell.fill),
                                'font': data_font,
                                'border': copy(header_cell.border),
                                'alignment': copy(header_cell.alignment),
                                'number_format': header_cell.number_format
                            }
                        
                        # Escribir datos aplicando formato de encabezados
                        for r, row_data in enumerate(dataframe_to_rows(df, index=False, header=False), 2):
                            for c, value in enumerate(row_data, 1):
                                if c <= ws.max_column:
                                    # Escribir valor
                                    cell = ws.cell(r, c, value)
                                    
                                    # Aplicar formato de la fila 1 (encabezados)
                                    if c in header_styles:
                                        style = header_styles[c]
                                        cell.fill = style['fill']
                                        cell.font = style['font']
                                        cell.border = style['border']
                                        cell.alignment = style['alignment']
                                        cell.number_format = style['number_format']
                        
                        Logger.write_log().log_all('info', f'{sheet_name}: {len(df)} registros', logger_console, logger)
                    elif not df.empty:
                        Logger.write_log().log_all('warning', f'Hoja {sheet_name} no existe en template', logger_console, logger)
                
                Logger.write_log().log_all('info', 'SOE sin cambios', logger_console, logger)
                wb.save(checklist_path_save)
                Logger.write_log().log_all('info', f'Checklist guardado: {checklist_path_save}', logger_console, logger)

            except Exception as e:
                Logger.write_log().log_all('error', f'Error checklist: {e}', logger_console, logger)      
                
        guardar_checklist(status_df_checklist, analog_df_checklist)
        
        def guardar_scada_load(status_df_orig, analog_df_orig, iccp_df_orig):
            """Guardar todas las señales en la plantilla ScadaLoad.xlsx"""
            # Filtrar DataFrames con datos
            cmd_columns = ['Command Type', 'Command Address', 'Scada Key', 'Type', 'Name', 'RTU']
            
            # Verificar si status_df_orig está vacío antes de intentar acceder a columnas
            if not status_df_orig.empty:
                cmd_sheet = status_df_orig[status_df_orig['Type'].isin(['T_I&C','T_CTL','T_R/L'])]
            else:
                cmd_sheet = pd.DataFrame()
                
            if not cmd_sheet.empty and all(col in cmd_sheet.columns for col in cmd_columns):
                cmd_sheet = cmd_sheet[cmd_columns]
                cmd_sheet['Indic'] = range(1, len(cmd_sheet) + 1)
                cmd_sheet['ControlParm'] = cmd_sheet['Scada Key'].notna().astype(int)
                cmd_sheet['Control Subtype'] = cmd_sheet['Command Type'].apply(lambda x: 1 if x == 'DC' else 0)
                cmd_sheet['Mode'] = 'ON'
                cmd_sheet['Control Type'] = cmd_sheet['Command Type'].map({'RC': 'Raise-Lower', 'SC': 'Close Only', 'DC': 'Open-Close'})
                cmd_sheet['Control Format'] = 'Direct'
                cmd_sheet['ScadaType'] = 'STATUS'
                
                # Renombrar columnas según el formato requerido
                cmd_sheet = cmd_sheet.rename(columns={'Scada Key': 'ScadaKey','RTU': 'pRTU', 'Command Address': 'ControlAddress'})
                # Ordenar columnas en el orden específico requerido
                column_order = ['Indic', 'ScadaKey', 'pRTU', 'ControlAddress', 'ControlParm','Control Subtype', 'Mode', 'Control Type', 'Control Format', 'ScadaType']
                cmd_sheet = cmd_sheet[column_order]
            else:
                # Si no hay datos válidos para comandos, usar DataFrame vacío
                cmd_sheet = pd.DataFrame()
                
            sheets_data = {name: df.copy() for name, df in 
                          [('STATUS', status_df_orig), ('ANALOG', analog_df_orig), ('ICCP', iccp_df_orig), ('CONTROLS(FEP)', cmd_sheet)]
                          if df is not None and not df.empty}
            
            if not sheets_data:
                Logger.write_log().log_all('warning', 'No hay datos para generar ScadaLoad', logger_console, logger)
                return
            
            try:
                scada_load_template_path = get_resource_path("templates/ScadaLoad.xlsx")
                scada_load_save_path = os.path.join(carpeta, 'ScadaLoad_completo.xlsx')
                wb = load_workbook(scada_load_template_path, keep_links=False, data_only=False)
                Logger.write_log().log_all('info', f'Plantilla ScadaLoad cargada: {scada_load_template_path}', logger_console, logger)
                
                for sheet_name, df_data in sheets_data.items():
                    if sheet_name not in wb.sheetnames:
                        Logger.write_log().log_all('warning', f'Hoja {sheet_name} no existe en la plantilla', logger_console, logger)
                        continue
                        
                    ws = wb[sheet_name]
                    
                    # Manejo especial para CONTROLS(FEP)
                    if sheet_name == 'CONTROLS(FEP)':
                        # Capturar formato específicamente de la fila 2 ANTES de limpiar
                        styles = {}
                        for col_idx in range(1, min(ws.max_column + 1, len(df_data.columns) + 1)):
                            # Para CONTROLS(FEP), usar formato específicamente de fila 2
                            cell = ws.cell(2, col_idx)
                            font = copy(cell.font)
                            font.bold = False
                            styles[col_idx] = {
                                'fill': copy(cell.fill), 'font': font, 'border': copy(cell.border),
                                'alignment': copy(cell.alignment), 'number_format': cell.number_format
                            }
                        
                        # Limpiar datos existentes desde fila 2
                        if ws.max_row > 1:
                            ws.delete_rows(2, ws.max_row - 1)
                        
                        # Escribir datos desde fila 2
                        for r, row_data in enumerate(dataframe_to_rows(df_data, index=False, header=False), 2):
                            for c, value in enumerate(row_data, 1):
                                if c <= len(df_data.columns) and c in styles:
                                    cell = ws.cell(r, c, value)
                                    for attr, val in styles[c].items():
                                        setattr(cell, attr, copy(val) if hasattr(val, '__dict__') else val)
                        
                        # Configurar filtros en fila 1 y congelado en fila 2
                        if ws.max_row > 1:
                            last_col = max(len(df_data.columns), ws.max_column)
                            ws.auto_filter.ref = f"A1:{ws.cell(ws.max_row, last_col).coordinate}"
                            ws.freeze_panes = "A2"
                    else:
                        # Manejo normal para otras hojas
                        # Limpiar datos existentes desde fila 3
                        if ws.max_row > 2:
                            ws.delete_rows(3, ws.max_row - 2)
                        
                        # Capturar formato de fila 2 sin negrilla
                        styles = {}
                        for col_idx in range(1, min(ws.max_column + 1, len(df_data.columns) + 1)):
                            cell = ws.cell(2, col_idx)
                            font = copy(cell.font)
                            font.bold = False
                            styles[col_idx] = {
                                'fill': copy(cell.fill), 'font': font, 'border': copy(cell.border),
                                'alignment': copy(cell.alignment), 'number_format': cell.number_format
                            }
                        
                        # Escribir datos con formato
                        for r, row_data in enumerate(dataframe_to_rows(df_data, index=False, header=False), 3):
                            for c, value in enumerate(row_data, 1):
                                if c <= len(df_data.columns) and c in styles:
                                    cell = ws.cell(r, c, value)
                                    for attr, val in styles[c].items():
                                        setattr(cell, attr, copy(val) if hasattr(val, '__dict__') else val)
                        
                        # Configurar filtros y congelado
                        if ws.max_row > 2:
                            last_col = max(len(df_data.columns), ws.max_column)
                            ws.auto_filter.ref = f"A2:{ws.cell(ws.max_row, last_col).coordinate}"
                            ws.freeze_panes = "A3"
                    
                    Logger.write_log().log_all('info', f'Hoja {sheet_name}: {len(df_data)} registros escritos', logger_console, logger)
                
                wb.save(scada_load_save_path)
                wb.close()
                Logger.write_log().log_all('info', f'ScadaLoad completo guardado: {scada_load_save_path}', logger_console, logger)
                
            except Exception as e:
                Logger.write_log().log_all('error', f'Error al generar ScadaLoad: {e}', logger_console, logger)
        
        # Obtener la hoja ICCP original si existe
        iccp_df_original = dfs.get('ICCP', pd.DataFrame())
        
        # Llamar a la función para guardar ScadaLoad
        guardar_scada_load(status_df_checklist, analog_df_checklist, iccp_df_original)
        
        # Eliminar archivo temporal Señales_with_keys.xlsx después de procesarlo
        if os.path.exists(excel_path):
            os.remove(excel_path)
            Logger.write_log().log_all('info', f'Archivo temporal eliminado: {excel_path}', logger_console, logger)
        
        Logger.write_log().log_all('info','Proceso completado',logger_console,logger)

    except Exception as e:
        Logger.write_log().log_all('error',f'Error en procesamiento: {e}',logger_console,logger)
        raise

if __name__=="__main__":
    procesar_datos()
