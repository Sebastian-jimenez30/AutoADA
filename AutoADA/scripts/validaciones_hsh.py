import os
import numpy as np
import pandas as pd
from openpyxl import load_workbook
import json
import argparse
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def _runtime_root() -> str:
    """Raz de trabajo ESCRITURA/LECTURA: CWD (donde corre el .exe)."""
    return os.getcwd()

def get_paths(site: str):
    rt = _runtime_root()
    return {
        'LOOKUP':        os.path.join(rt, 'out', site, 'HSH',   'lookup_table.csv'),
        'GROUP':         os.path.join(rt, 'out', site, 'HSH',   'groups.csv'),
        'SCADA_STATUS':  os.path.join(rt, 'out', site, 'SCADA', '10_4.csv'),
        'SCADA_ANALOGS': os.path.join(rt, 'out', site, 'SCADA', '10_5.csv'),
    }

def safe_read_csv(path, **kwargs):
    try:
        logger.info(f"Cargando archivo: {path}")
        return pd.read_csv(path, **kwargs)
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {path}")
        raise
    except Exception as e:
        logger.error(f"Error leyendo {path}: {e}")
        raise

def convertir(group_df, respaldo_group_df, look_df, respaldo_look_df,
              scada_analogs_df, scada_status_df, respaldo_scada_analogs_df, respaldo_scada_status_df):
    logger.info('Iniciando funcin convertir')

    scada_status_df.loc[:, 'Seal'] = 'SCADA_STATUS'
    scada_analogs_df.loc[:, 'Seal'] = 'SCADA_ANALOG'
    respaldo_scada_status_df.loc[:, 'Seal'] = 'SCADA_STATUS'
    respaldo_scada_analogs_df.loc[:, 'Seal'] = 'SCADA_ANALOG'

    scada_status_df = scada_status_df[['Key', 'Archive_group', 'Seal']]
    scada_analogs_df = scada_analogs_df[['Key', 'Archive_group', 'Seal']]
    respaldo_scada_status_df = respaldo_scada_status_df[['Key', 'Archive_group', 'Seal']]
    respaldo_scada_analogs_df = respaldo_scada_analogs_df[['Key', 'Archive_group', 'Seal']]

    scada_total_site1 = pd.concat([scada_status_df, scada_analogs_df])
    scada_total_site2 = pd.concat([respaldo_scada_status_df, respaldo_scada_analogs_df])

    def safe_int_conversion(x):
        try:
            x = int(x)
            # Si est fuera del rango permitido, devolvemos todo en ceros
            if x > 256 or x < -256:
                return '00000000'
            # Si es negativo entre -1 y -255, lo ajustamos sumando 256
            if -255 <= x <= -1:
                x += 256
            # Convertimos a binario de 8 bits
            return format(x, 'b').zfill(8)
        except (ValueError, OverflowError):
            return '00000000'

    scada_total_site1['Archive_group_bina'] = scada_total_site1['Archive_group'].apply(safe_int_conversion)
    scada_total_site2['Archive_group_bina'] = scada_total_site2['Archive_group'].apply(safe_int_conversion)

    # Funcin para clasificar segn los bits menos significativos
    def clasificar(seal, binario):
        bits = binario[-2:]  # Tomamos los dos ltimos bits
        if bits == "01" and seal == "SCADA_STATUS":
            return "STATUS_N"
        elif bits == "10" and seal == "SCADA_ANALOG":
            return "ANALOG_N"
        elif bits == "01" and seal == "SCADA_ANALOG":
            return "ANALOG_N-2"
        elif bits == "00":
            return "APAGADO"
        elif bits == "11":
            return "ERROR"
        else:
            return "DESCONOCIDO"  # Para casos no contemplados

    scada_total_site1["Colector"] = scada_total_site1.apply(
        lambda row: clasificar(row["Seal"], row["Archive_group_bina"]), axis=1
    )
    scada_total_site2["Colector"] = scada_total_site2.apply(
        lambda row: clasificar(row["Seal"], row["Archive_group_bina"]), axis=1
    )

    # Unir scada_total con group_ITCO y group_TRA
    group_site_sc = pd.merge(scada_total_site1, group_df, left_on='Key', right_on='UID3', how='right').rename(columns={'UID3': 'Key_g'})
    group_respaldo_sc = pd.merge(scada_total_site2, respaldo_group_df, left_on='Key', right_on='UID3', how='right').rename(columns={'UID3': 'Key_g'})
    group_site_sc['Key-Type'] = group_site_sc['Key_g'] + '.' + group_site_sc['PointName']
    group_respaldo_sc['Key-Type'] = group_respaldo_sc['Key_g'] + '.' + group_respaldo_sc['PointName']

    # Seleccin de columnas de inters
    cols_group = [
        'Key-Type', 'Key_g', 'PointName', 'LinkAttributeValue', 'Colector', 'Transform_id',
        'CPID', 'UID', 'IsAuthorized', 'IsPointValid', 'IsIgnored',
        'PointErrorMessage', 'TagCreationErrorMessage', 'TagErrorMessages'
    ]
    group_site_sc = group_site_sc[cols_group]
    group_respaldo_sc = group_respaldo_sc[cols_group]

    group_site_sc = group_site_sc.rename(columns={'Key_g': 'Key', 'PointName': 'Type', 'LinkAttributeValue': 'Value'})
    group_respaldo_sc = group_respaldo_sc.rename(columns={'Key_g': 'Key', 'PointName': 'Type', 'LinkAttributeValue': 'Value'})

    look_df = look_df.rename(columns={'Key': 'Key-Type'})
    respaldo_look_df = respaldo_look_df.rename(columns={'Key': 'Key-Type'})

    # Procesamiento de look_ITCO y look_TRA
    for df in [look_df, respaldo_look_df]:
        # Split safely with exactly 2 columns handling edge cases
        split_result = df['Key-Type'].str.split('.', expand=True, n=1)
        if split_result.shape[1] == 1:
            # Only one column, no dot found - treat as Key with empty Type
            df['Key'] = split_result[0]
            df['Type'] = ''
        else:
            # Two columns, normal case
            df['Key'] = split_result[0]
            df['Type'] = split_result[1]

    look_site_sc = pd.merge(scada_total_site1, look_df, left_on='Key', right_on='Key', how='right')[
        ['Key-Type', 'Key', 'Type', 'Value', 'Seal', 'Colector']
    ]
    look_respaldo_sc = pd.merge(scada_total_site2, respaldo_look_df, left_on='Key', right_on='Key', how='right')[
        ['Key-Type', 'Key', 'Type', 'Value', 'Seal', 'Colector']
    ]

    # Concatenacin final
    groupT_sc = pd.concat([group_site_sc, group_respaldo_sc], ignore_index=True)

    logger.info('Funcin convertir finalizada')
    return group_site_sc, group_respaldo_sc, look_site_sc, look_respaldo_sc, groupT_sc


def inicializar_dataframes(site, respaldo):
    # Cargar archivos para ambos sitios
    p_site = get_paths(site)
    p_respaldo = get_paths(respaldo)

    look_site = safe_read_csv(p_site['LOOKUP'], dtype=str)
    look_respaldo = safe_read_csv(p_respaldo['LOOKUP'], dtype=str)
    group_site = safe_read_csv(p_site['GROUP'], dtype=str)
    group_respaldo = safe_read_csv(p_respaldo['GROUP'], dtype=str)

    scada_status_site = safe_read_csv(p_site['SCADA_STATUS'], dtype=str).dropna(how='all')
    scada_analogs_site = safe_read_csv(p_site['SCADA_ANALOGS'], dtype=str).dropna(how='all')
    scada_status_respaldo = safe_read_csv(p_respaldo['SCADA_STATUS'], dtype=str).dropna(how='all')
    scada_analogs_respaldo = safe_read_csv(p_respaldo['SCADA_ANALOGS'], dtype=str).dropna(how='all')

    # Llamar convertir
    group_site_sc, group_respaldo_sc, look_site_sc, look_respaldo_sc, groupT_sc = convertir(
        group_site, group_respaldo, look_site, look_respaldo,
        scada_analogs_site, scada_status_site, scada_analogs_respaldo, scada_status_respaldo
    )
    return {
        'group_sc': group_site_sc,
        'look_sc': look_site_sc,
        'group': group_site,
        'respaldo_group_sc': group_respaldo_sc,
        'respaldo_look_sc': look_respaldo_sc,
        'respaldo_group': group_respaldo,
        'groupT_sc': groupT_sc
    }

#---------------------------------------------------------------------------------------------------
def generar_archivos_eliminacion(validaciones_df, group_site, group_respaldo, folder_name, site, respaldo):
    from pandas import merge, DataFrame

    # Renombrar columnas para hacer merge
    df_group_site = group_site.rename(columns={'UID3': 'Key', 'PointName': 'Type', 'LinkAttributeValue': 'Value'})
    df_group_respaldo = group_respaldo.rename(columns={'UID3': 'Key', 'PointName': 'Type', 'LinkAttributeValue': 'Value'})

    # Filtrar seales a eliminar
    eliminar_site = validaciones_df[validaciones_df['Validacion'].isin([f'Eliminar de groups de {site}', 'Eliminar'])]
    eliminar_respaldo = validaciones_df[validaciones_df['Validacion'].isin([f'Eliminar de groups de {respaldo}'])]

    # Merge para obtener CPID y UID
    result_site = merge(eliminar_site, df_group_site, how='inner', on=['Key', 'Type'])
    result_respaldo = merge(eliminar_respaldo, df_group_respaldo, how='inner', on=['Key', 'Type'])

    # Formato de salida
    def formatear(df):
        df_out = df[['CPID', 'UID']].copy()
        df_out['Delete'] = 'Delete'
        df_out['Purge'] = 'Purge'
        df_out['Continuous'] = 'CONTINUOUS'
        df_out[['Columna_vacia1', 'Columna_vacia2']] = ''
        return (
            df_out[['Delete', 'CPID', 'UID', 'Continuous', 'Columna_vacia1', 'Columna_vacia2']],
            df_out[['Purge', 'CPID', 'UID', 'Continuous', 'Columna_vacia1', 'Columna_vacia2']]
        )

    total_site1, total_site2 = formatear(result_site)
    total_respaldo1, total_respaldo2 = formatear(result_respaldo)

    # Timestamp
    time1 = int((datetime.now(timezone.utc) + timedelta(hours=5)).timestamp())

    # Crear carpeta
    os.makedirs(folder_name, exist_ok=True)

    # Guardar archivos
    def guardar(nombre, df):
        path = os.path.join(folder_name, nombre)
        with open(path, 'w') as f:
            f.write(f'header,2,{time1}\n')
        df.to_csv(path, mode='a', index=False, header=False)

    if not total_site1.empty:
        guardar(f'Delete_UIDs_{site.lower()}.csv', total_site1)
    if not total_site2.empty:
        guardar(f'Purge_UIDs_{site.lower()}.csv', total_site2)
    if not total_respaldo1.empty:
        guardar(f'Delete_UIDs_{respaldo.lower()}.csv', total_respaldo1)
    if not total_respaldo2.empty:
        guardar(f'Purge_UIDs_{respaldo.lower()}.csv', total_respaldo2)

    print(f"Archivos de eliminacin generados en la carpeta '{folder_name}'")

#---------------------------------------------------------------------------------------------------------------------
# Funcin para generar archivos de LookUp Table
def generar_archivos_lookup(combined_df, output_folder, site, respaldo):
    # Definir los criterios de validacin
    df_crear_site = [f'Falta en LookUp Table del site 1', 'Crear en LookUp Table']
    df_crear_respaldo = [f'Falta en LookUp Table del site 2', 'Crear en LookUp Table']

    # Filtrar y crear columnas formateadas
    df_crear1 = combined_df[combined_df['Validacion'].isin(df_crear_site)].copy()
    df_crear2 = combined_df[combined_df['Validacion'].isin(df_crear_respaldo)].copy()

    df_crear1 = df_crear1.assign(
        Columna1=df_crear1['Key'].astype(str) + '.' + df_crear1['Type'].astype(str) + ',' + df_crear1['Value'].astype(str)
    )[["Columna1"]]
    df_crear2 = df_crear2.assign(
        Columna1=df_crear2['Key'].astype(str) + '.' + df_crear2['Type'].astype(str) + ',' + df_crear2['Value'].astype(str)
    )[["Columna1"]]

    # Crear carpeta si no existe
    os.makedirs(output_folder, exist_ok=True)

    # Guardar archivos solo si hay datos
    if not df_crear1.empty:
        df_crear1.to_csv(os.path.join(output_folder, f'LookUp_{site.lower()}.csv'), mode='a', index=False, header=False)
    if not df_crear2.empty:
        df_crear2.to_csv(os.path.join(output_folder, f'LookUp_{respaldo.lower()}.csv'), mode='a', index=False, header=False)

    print(f"Archivos de LookUp generados en: {output_folder}")

# ===================== FIN DE LIMPIEZA =====================
#Funcion para validar que seales de lookUp_site (sitio a validar) no estan en groups de ambos sitios
def validar_groupT_loookITCO1(groupsTotal, lookup_site, site):
    resultados = []

    df_no_scada_look = lookup_site[lookup_site['Colector'].isna()].copy()
    df_no_scada_look['Validacion'] = 'Est en la lookup table, pero no en SCADA.'
    df_no_scada_look['Etiqueta'] = 'ERROR'
    df_no_scada_look = df_no_scada_look[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
    resultados.append(df_no_scada_look)

    # Eliminar filas con valores vacos en la columna 'Colector'
    lookup_site = lookup_site[lookup_site['Colector'].notna()]

    # Crear el conjunto de "Key-Type" en groupT
    groupT_set = set(groupsTotal["Key-Type"])

    # Filtrar look_Up_site para obtener las filas que no estn en groupT
    df2 = lookup_site[~lookup_site["Key-Type"].isin(groupT_set)].copy()

    # Agregar informacin de validacin
    df2['Validacion'] = f'No existe en groups'
    df2['Etiqueta'] = 'WARNING'

    # Seleccionar las columnas necesarias
    df2 = df2[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
    resultados.append(df2)

    return pd.concat(resultados, ignore_index=True) if resultados else pd.DataFrame(columns=['Key', 'Type', 'Value', 'Validacion', 'Etiqueta'])

#------------------------------------------------------------------------------------------------------------------------------------------------
def errores(groups_site, look_site):
    resultados = []

    # Filtrar errores de PointErrorMessage
    df_point_error = groups_site[groups_site['PointErrorMessage'].notna()].copy()
    if not df_point_error.empty:
        df_point_error['Validacion'] = df_point_error['PointErrorMessage']
        df_point_error['Etiqueta'] = 'ERROR'
        resultados.append(df_point_error[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']])
        groups_site = groups_site[groups_site['PointErrorMessage'].isna()]

    # Filtrar errores de TagCreationErrorMessage
    df_tag_error = groups_site[groups_site['TagCreationErrorMessage'].notna()].copy()
    if not df_tag_error.empty:
        df_tag_error['Validacion'] = df_tag_error['TagCreationErrorMessage']
        df_tag_error['Etiqueta'] = 'ERROR'
        resultados.append(df_tag_error[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']])
        groups_site = groups_site[groups_site['TagCreationErrorMessage'].isna()]

    # Lista de errores adicionales
    errores_list = [
        ('IsAuthorized', 'False', 'Autorizado no vlido'),
        ('IsPointValid', 'False', 'Punto no vlido'),
        ('IsIgnored', 'True', 'Ignorado vlido')
    ]

    for columna, valor, mensaje in errores_list:
        df_error = groups_site[groups_site[columna] == valor].copy()
        if not df_error.empty:
            df_error['Validacion'] = mensaje
            df_error['Etiqueta'] = 'ERROR'
            resultados.append(df_error[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']])
            groups_site = groups_site[groups_site[columna] != valor]

    # Filas sin 'Colector'
    df_no_scada_groups = groups_site[groups_site['Colector'].isna()].copy()
    if not df_no_scada_groups.empty:
        df_no_scada_groups['Validacion'] = 'No existe en Scada_groups'
        df_no_scada_groups['Etiqueta'] = 'ERROR'
        df_no_scada_groups = df_no_scada_groups[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
        resultados.append(df_no_scada_groups)
        groups_site = groups_site[groups_site['Colector'].notna()]

    # groups que no existen en lookup_table
    looksite_set = set(look_site["Key-Type"])
    df_no_groups_look = groups_site[~groups_site["Key-Type"].isin(looksite_set)].copy()
    df_no_groups_look['Validacion'] = 'Crear en LookUp Table'
    df_no_groups_look['Etiqueta'] = 'CRITICAL'
    df_no_groups_look = df_no_groups_look[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
    resultados.append(df_no_groups_look)

    resultado = pd.concat(resultados, ignore_index=True) if resultados else pd.DataFrame(columns=['Key', 'Type', 'Value', 'Validacion', 'Etiqueta'])
    return groups_site, resultado

#------------------------------------------------------------------------------------------------------------------------------------------------
def validar_duplicados2(df):
    duplicados = df[df.duplicated(subset=['Value'], keep=False)].copy()
    if not duplicados.empty:
        duplicados['Validacion'] = 'Duplicado en Groups'
        duplicados['Etiqueta'] = 'ERROR'
    return duplicados[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']] if not duplicados.empty else pd.DataFrame()

#------------------------------------------------------------------------------------------------------------------------------------------------
def validar_datos_repetidos_groups(df1, df2):
    df1_filtrado = df1[df1["Key-Type"].isin(df2["Key-Type"])][['Key', 'Type', 'Value']]
    df2_filtrado = df1[df1["Value"].isin(df2["Value"])][['Key', 'Type', 'Value']]
    df_filtrado = pd.concat([df1_filtrado, df2_filtrado]).drop_duplicates(keep='first')
    if df_filtrado.empty:
        return pd.DataFrame(columns=['Key', 'Type', 'Value', 'Validacion', 'Etiqueta'])
    df_filtrado['Validacion'] = 'Existe en ambos groups'
    df_filtrado['Etiqueta'] = 'WARNING'
    return df_filtrado[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]

#------------------------------------------------------------------------------------------------------------------------------------------------
def validacion_scada(groups_site):
    groups_site = groups_site[groups_site['Type'] == 'Q']
    resultados = []

    Seal_status = groups_site[
        (groups_site['Transform_id'] == 'STATUS_N') & (groups_site['Colector'] == 'APAGADO')
    ][['Key', 'Type', 'Value']].copy()
    Seal_status['Validacion'] = 'Encender Bit de envo colector 1'
    Seal_status['Etiqueta'] = 'WARNING'
    resultados.append(Seal_status)

    substrings = [':P', ':Q', ':I2', ':U2', ':TAP', ':TAP2']
    def check_substrings(value):
        return any(sub in value for sub in substrings)

    df_estimated = groups_site[
        (groups_site['Transform_id'] == 'ANALOG_N') & (groups_site['Value'].apply(check_substrings))
    ].copy()

    df_not_estimated = groups_site[
        ((groups_site['Transform_id'] == 'ANALOG_N') & (~groups_site['Value'].apply(check_substrings)))
    ][['Key', 'Type', 'Value']].copy()
    df_not_estimated['Validacion'] = 'Encender Bit de envo colector sebas'
    df_not_estimated['Etiqueta'] = 'Warning'
    resultados.append(df_not_estimated)

    def create_message_and_label(row):
        if row['Colector'] == 'ANALOG_N-2':
            return "Agregar punto .estimated", "WARNING"
        elif row['Colector'] == 'ERROR':
            return "Varios Bit de envo activados", "WARNING"
        elif row['Colector'] == 'APAGADO':
            return "Encender colector 2(ANALOG_N)", "WARNING"
        else:
            return None, None

    df_estimated[['Validacion', 'Etiqueta']] = df_estimated.apply(create_message_and_label, axis=1, result_type='expand')
    filtered_df = df_estimated.dropna(subset=['Validacion', 'Etiqueta'])[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
    resultados.append(filtered_df)

    df_analog_n2 = groups_site[groups_site['Transform_id'] == 'ANALOG_N-2'].copy()

    def create_message_and_label1(row):
        if row['Colector'] == 'ANALOG_N':
            return "Eliminar .Esmitated", "WARNING"
        elif row['Colector'] == 'ERROR':
            return "Varios Bit de envo activados", "WARNING"
        elif row['Colector'] == 'APAGADO':
            return "Encender colector 1(ANALOG_N-2)", "WARNING"
        else:
            return None, None

    result_apply = df_analog_n2.apply(create_message_and_label1, axis=1, result_type='expand')
    mask_valid = result_apply.notnull().all(axis=1)
    if mask_valid.any():
        df_analog_n2_valid = df_analog_n2.loc[mask_valid].copy()
        df_analog_n2_valid[['Validacion', 'Etiqueta']] = result_apply[mask_valid].values
        df_analog_n2_valid = df_analog_n2_valid[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
        resultados.append(df_analog_n2_valid)

    resultado = pd.concat(resultados, ignore_index=True) if resultados else pd.DataFrame(columns=['Key', 'Type', 'Value', 'Validacion', 'Etiqueta'])
    return resultado

#------------------------------------------------------------------------------------------------------------------------------------------------
def duplicados_lookup_Site(df):
    duplicados = df[df.duplicated(subset=['Value'], keep='first')].copy()
    if not duplicados.empty:
        duplicados.loc[:, 'Validacion'] = 'Duplicado en LookUp Table'
        duplicados.loc[:, 'Etiqueta'] = 'ERROR'
        return duplicados[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
    else:
        return pd.DataFrame(columns=['Key', 'Type', 'Value', 'Validacion', 'Etiqueta'])

#------------------------------------------------------------------------------------------------------------------------------------------------
def comparar_lookup(df1, df2, df3, df4):
    concatenado = pd.concat([df1, df2], keys=['df1', 'df2']).reset_index(level=0).rename(columns={'level_0': 'Source'})
    diferencias = concatenado.drop_duplicates(subset=['Key-Type', 'Value'], keep=False).copy()
    if diferencias.empty:
        return pd.DataFrame(columns=['Key', 'Type', 'Value', 'Validacion', 'Etiqueta'])

    diferencias['Validacion'] = diferencias['Source'].map({
        'df1': 'Falta en LookUp Table del site 1',
        'df2': 'Falta en LookUp Table del site 2'
    })
    diferencias['Etiqueta'] = 'CRITICAL'

    df_crear1 = diferencias[diferencias['Validacion'] == 'Falta en LookUp Table del site 1'].copy()
    df_crear2 = diferencias[diferencias['Validacion'] == 'Falta en LookUp Table del site 2'].copy()

    def validar_keys(df_a, df_b, mensaje):
        df_a = df_a.copy()
        df_a['coincidencia'] = df_a['Key-Type'].isin(df_b['Key-Type'])
        df_a['Validacion'] = df_a.apply(lambda row: row['Validacion'] if row['coincidencia'] else mensaje, axis=1)
        df_a.drop(columns=['coincidencia'], inplace=True)
        return df_a

    result1 = validar_keys(df_crear1, df4, 'Eliminar en LookUp Table site 2')
    result2 = validar_keys(df_crear2, df3, 'Eliminar en LookUp Table site 1')
    total = pd.concat([result1, result2])[['Key', 'Type', 'Value', 'Validacion', 'Etiqueta']]
    if total.empty:
        return pd.DataFrame(columns=['Key', 'Type', 'Value', 'Validacion', 'Etiqueta'])
    return total

#------------------------------------------------------------------------------------------------------------------------------------------------
def validar(site, respaldo):
    logger.info(f"Iniciando validacin para: {site} (respaldo: {respaldo})")

    # Carpetas de salida SIEMPRE relativas al CWD
    rt = _runtime_root()
    output_folder = os.path.join(rt, 'out', f'Validaciones_{site}')
    output_folder_eliminacion_file = os.path.join(output_folder, 'Delete')
    os.makedirs(output_folder, exist_ok=True)

    excel_path = os.path.join(output_folder, f'Validaciones_{site}.xlsx')

    dfs = inicializar_dataframes(site, respaldo)

    groups_site_sin_errores, Val2 = errores(dfs['group_sc'], dfs['look_sc'])
    Val1 = validar_groupT_loookITCO1(dfs['groupT_sc'], dfs['look_sc'], site)
    Val3 = validar_duplicados2(groups_site_sin_errores)
    Val4 = validar_datos_repetidos_groups(groups_site_sin_errores, dfs['respaldo_group_sc'])
    Val5 = validacion_scada(groups_site_sin_errores)
    Val6 = duplicados_lookup_Site(dfs['look_sc'])
    Val7 = comparar_lookup(dfs['respaldo_look_sc'], dfs['look_sc'], groups_site_sin_errores, dfs['respaldo_group_sc'])

    total = pd.concat([Val1, Val2, Val3, Val4, Val5, Val6, Val7])

    generar_archivos_eliminacion(total, dfs['group'], dfs['respaldo_group'], output_folder_eliminacion_file, site, respaldo)
    generar_archivos_lookup(total, output_folder_eliminacion_file, site, respaldo)

    logger.info(f"Guardando resultados en {excel_path}")
    total.to_excel(excel_path, index=False)
    wb = load_workbook(excel_path)
    ws = wb.active
    ws.auto_filter.ref = ws.dimensions
    wb.save(excel_path)

    logger.info("Validacin finalizada correctamente.")
    return total

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Ejecutar validacin.')
    parser.add_argument('site', type=str, help='Nombre del grupo principal (ej: ITCO, REPS)')
    parser.add_argument('--respaldo', type=str, default=None, help='Nombre del grupo respaldo (ej: TRA, REPP). Si no se especifica, se infiere automticamente.')
    args = parser.parse_args()

    # Diccionario de correspondencias
    respaldo_map = {
        'ITCO': 'TRA',
        'TRA': 'ITCO',
        'REPS': 'REPP',
        'REPP': 'REPS'
    }

    site = args.site.upper()
    respaldo = args.respaldo.upper() if args.respaldo else respaldo_map.get(site)
    if not respaldo:
        raise ValueError(f"No se pudo inferir el respaldo para el site '{site}'. Especifquelo manualmente.")
    validar(site, respaldo)
