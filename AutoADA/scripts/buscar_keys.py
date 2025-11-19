"""
Busca un ScadaKey en las bases de datos SCADA, HSH y ODS para la empresa seleccionada
(one-file friendly: lee config desde bundle/CWD y escribe salidas en CWD)
"""
import argparse
import os
import sys
import pandas as pd
import json
import openpyxl
from openpyxl.styles import Font
import re
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

# ---------- Helpers de rutas ----------

def _bundle_base_dir() -> str:
    """Carpeta base para leer assets (config) cuando está congelado o en dev."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    # En desarrollo: si existe ./config, usa CWD; si no, la carpeta padre del archivo
    if os.path.isdir(os.path.join(os.getcwd(), "config")):
        return os.getcwd()
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def _runtime_base_dir() -> str:
    return os.getcwd()

# ---------- CLI ----------

def get_args():
    parser = argparse.ArgumentParser(description='Script para buscar un ScadaKey en Bases de Datos')
    parser.add_argument('empresa', type=str, help='Nombre de la empresa')
    parser.add_argument('ruta', type=str, help='Ruta del archivo excel con los ScadaKeys')
    return parser.parse_args()

# ---------- Config ----------

def get_config():
    base = _bundle_base_dir()
    cfg_path = os.path.join(base, 'config', 'buscar_key.json')
    if not os.path.isfile(cfg_path):
        # Fallback adicional por si corres desde la raíz y ya estás en CWD
        alt = os.path.join(os.getcwd(), 'config', 'buscar_key.json')
        if os.path.isfile(alt):
            cfg_path = alt
    with open(cfg_path, 'r', encoding='utf-8') as config_file:
        return json.load(config_file)


def load_db_labels():
    candidates = [
        os.path.join(_bundle_base_dir(), "config", "db_names.json"),
        os.path.join(os.getcwd(), "config", "db_names.json"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return {}
    return {}

DB_LABELS = load_db_labels()

def resolve_table_label(folder, table_name):
    label = DB_LABELS.get(table_name)
    if label:
        return label
    return f"{folder} {table_name}"


def split_db_table_label(label: str):
    if not label:
        return "", ""
    parts = label.split(' ', 1)
    db = parts[0].strip() if parts and parts[0] else ""
    rest = parts[1].strip() if len(parts) > 1 else ""
    if rest:
        rest = re.sub(r'[_]+', ' ', rest).strip()
    return db, rest


def regex_from_pattern(pattern):
    patron_escapado = re.escape(pattern.strip().upper()).replace('%', '.')
    return f"^{patron_escapado}$"

# ---------- Main ----------

def main():
    args = get_args()
    empresa = args.empresa
    ruta_excel_in = args.ruta

    FIXED_NAME = "Find_Key.xlsx"  # nombre fijo de salida

    # Lee el archivo Excel (columna A, omite primera fila)
    df = pd.read_excel(ruta_excel_in, header=None, skiprows=1, dtype=str)
    keys2 = df[0].tolist()
    keys = [str(item).strip().upper() for item in keys2]

    # Valida llaves (8 caracteres alfanuméricos o con %)
    def es_key_valida(k: str) -> bool:
        k = k.strip().upper()
        return ('%' in k) or (re.match(r'^[A-Z0-9]{8}$', k) is not None)

    keys = [k for k in keys if es_key_valida(k)]

    # Directorios de salida en CWD
    runtime_base = _runtime_base_dir()
    out_root = os.path.join(runtime_base, "out")
    log_dir  = os.path.join(runtime_base, "log")
    topath   = os.path.join(out_root, "Find_key")
    os.makedirs(topath, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # Directorio base de datos convertidas (out/<EMPRESA>/SCADA|HSH|ODSTXT)
    directorio_out = out_root

    # Log
    log_path = os.path.join(log_dir, "buscar_keys.log")
    logger, logger_console = Logger.initlog(log_path)
    Logger.write_log().log_all("info", f"Inicio busqueda keys empresa {empresa}", logger_console, logger)

    # Config
    config = get_config()
    Logger.write_log().log_all("info", "Configuracion de busqueda cargada", logger_console, logger)

    # Resultados
    results = pd.DataFrame(columns=['Key', 'DB', 'Table', 'Field', 'Record'])
    keys_encontradas: list[str] = []

    # Recorre SCADA / HSH / ODSTXT
    for folder in ['SCADA', 'HSH', 'ODSTXT']:
        folder_path = os.path.join(directorio_out, empresa, folder)
        Logger.write_log().log_all("info", f"Buscando en {folder}", logger_console, logger)
        if not os.path.exists(folder_path):
            continue

        for file in os.listdir(folder_path):
            if not file.endswith('.csv'):
                continue

            file_name = os.path.splitext(file)[0]
            if file_name not in config:
                continue

            nombres_columnas = config[file_name]
            df_csv = pd.read_csv(os.path.join(folder_path, file), dtype=str, low_memory=False)
            table_name = file_name

            # Selección de columnas según archivo
            if file == 'lookup_table.csv':
                df_filtrado = df_csv.copy()
                df_filtrado[3] = df_filtrado[nombres_columnas[0]].str.split('.').str[0]
                df_filtrado = df_filtrado.iloc[:, [3, 0, 1]]

            elif file == 'groups.csv':
                df_filtrado = df_csv[nombres_columnas + ['CPID', 'LinkAttributeValue']].copy()

            else:
                indices_columnas = [0] + [df_csv.columns.get_loc(nombre_columna) for nombre_columna in nombres_columnas]
                df_filtrado = df_csv.iloc[:, indices_columnas].copy()
                df_filtrado = df_filtrado.dropna(subset=[df_filtrado.columns[0]])

            Logger.write_log().log_all(
                "info",
                f"Archivo {resolve_table_label(folder, table_name)} listo",
                logger_console,
                logger,
            )

            # Búsquedas
            for column in df_filtrado.columns:
                # Prepara columna limpia una sola vez
                def limpiar_valor(val):
                    val_str = str(val).strip().upper()
                    if re.match(r'^\d+\.0$', val_str):  # quita .0 de números
                        val_str = val_str.split('.')[0]
                    return val_str

                col_tmp = df_filtrado[column].apply(limpiar_valor).astype(str)
                col_tmp = col_tmp[col_tmp.str.match(r'^[A-Z0-9]+$', na=False)]
                df_filtrado['__col_temp__'] = col_tmp

                for current_key in keys:
                    regex = regex_from_pattern(current_key).replace('.', '[A-Z0-9]')
                    found_rows = df_filtrado[df_filtrado['__col_temp__'].str.match(regex, na=False)]
                    if found_rows.empty:
                        continue

                    if folder == 'SCADA':
                        file_name_only = os.path.splitext(file)[0]
                        table_label = resolve_table_label(folder, file_name_only)
                        db_display, table_display = split_db_table_label(table_label)
                        if not db_display:
                            db_display = 'SCADA'
                        if not table_display:
                            table_display = re.sub(r'[_]+', ' ', file_name_only).strip()

                        for _, row in found_rows.iterrows():
                            try:
                                record_value = int(row[df_filtrado.columns[0]])
                            except Exception:
                                record_value = row[df_filtrado.columns[0]]
                            key_encontrada = row[column]
                            Logger.write_log().log_all(
                                "info",
                                f"Key {key_encontrada} coincide con {current_key} en {table_label} campo {column} registro {record_value}",
                                logger_console, logger)
                            keys_encontradas.append(key_encontrada)
                            results = pd.concat([results, pd.DataFrame({
                                'Key': [key_encontrada], 'DB': [db_display], 'Table': [table_display],
                                'Record': [record_value], 'Field': [column]
                            })], ignore_index=True)

                    if folder == 'ODSTXT':
                        for index in found_rows.index:
                            row = found_rows.loc[index]
                            full_row = df_csv.loc[index]  # fila completa del CSV original
                            file_name_only = os.path.splitext(file)[0]
                            table_label = resolve_table_label(folder, file_name_only)
                            unifilar_name_only = os.path.splitext(full_row.iloc[0])[0].split('.')[0]
                            key_encontrada = row[column]
                            nivel_tension = full_row.iloc[1]
                            location = full_row.iloc[5]
                            Logger.write_log().log_all(
                                "info",
                                f"Key {key_encontrada} coincide con {current_key} en {table_label} diagrama {unifilar_name_only} campo {column}",
                                logger_console, logger)
                            keys_encontradas.append(key_encontrada)
                            results = pd.concat([results, pd.DataFrame({
                                'Key': [key_encontrada], 'DB': ['ODS'], 'Table': [file_name_only],
                                'Field': [unifilar_name_only], 'NivelTension': [nivel_tension], 'Location': [location]
                            })], ignore_index=True)

                    if folder == 'HSH':
                        for _, row in found_rows.iterrows():
                            record = row[df_filtrado.columns[2]]
                            nombre_columna = df_filtrado.columns[2]
                            table = os.path.splitext(file)[0]
                            table_label = resolve_table_label(folder, table)
                            key_encontrada = row[column]
                            Logger.write_log().log_all(
                                "info",
                                f"Key {key_encontrada} coincide con {current_key} en {table_label} campo {nombre_columna} registro {record}",
                                logger_console, logger)
                            keys_encontradas.append(key_encontrada)
                            results = pd.concat([results, pd.DataFrame({
                                'Key': [key_encontrada], 'DB': ['HSH'], 'Table': [table],
                                'Field': [nombre_columna], 'Record': [record]
                            })], ignore_index=True)

                # limpia columna temporal
                df_filtrado.drop(columns=['__col_temp__'], inplace=True)

    # Claves no encontradas
    claves_no_encontradas = list(set(keys) - set(keys_encontradas))
    for clave_no_encontrada in claves_no_encontradas:
        Logger.write_log().log_all('info', f'Key {clave_no_encontrada} sin resultados', logger_console, logger)
        results = pd.concat([results, pd.DataFrame({
            'Key': [clave_no_encontrada], 'DB': ['NaN'], 'Table': ['NaN'], 'Field': ['NaN'], 'Record': ['NaN']
        })], ignore_index=True)

    # Guardar Excel SIEMPRE como out/Find_key/Find_Key.xlsx (sobrescribe)
    ruta_excel_out = os.path.join(topath, FIXED_NAME)

    # Limpieza previa (y opcionalmente borra otros .xlsx para no acumular)
    try:
        if os.path.exists(ruta_excel_out):
            os.remove(ruta_excel_out)
        for f in os.listdir(topath):
            if f.endswith(".xlsx") and f != FIXED_NAME:
                try:
                    os.remove(os.path.join(topath, f))
                except Exception:
                    pass
    except Exception:
        pass

    results.to_excel(ruta_excel_out, index=False, header=True)

    # Formato con openpyxl
    wb = openpyxl.load_workbook(ruta_excel_out)
    hoja = wb.active

    for celda in hoja[1]:
        celda.font = Font(bold=True)

    for columna in hoja.columns:
        max_length = 0
        for celda in columna:
            try:
                max_length = max(max_length, len(str(celda.value)))
            except Exception:
                pass
        hoja.column_dimensions[columna[0].column_letter].width = (max_length + 2) * 1.2

    hoja.freeze_panes = 'A2'
    hoja.auto_filter.ref = hoja.dimensions
    wb.save(ruta_excel_out)

    Logger.write_log().log_all('info', f'Archivo {FIXED_NAME} creado', logger_console, logger)
    Logger.write_log().log_all('info', f'Keys con resultado {len(set(keys_encontradas))}', logger_console, logger)
    Logger.write_log().log_all('info', f'Keys sin resultado {len(claves_no_encontradas)}', logger_console, logger)
    Logger.write_log().log_all('info', 'Busqueda de keys finalizada', logger_console, logger)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

