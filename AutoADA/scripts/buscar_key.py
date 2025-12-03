"""
Busca un ScadaKey en las bases de datos SCADA, HSH y ODS para la empresa seleccionada
(one-file friendly: salidas en CWD, config desde bundle)
"""
import argparse
import os
import sys
import json
import re
import pandas as pd
import openpyxl
from openpyxl.styles import Font
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

name_file_out = "Find_Key.xlsx"

# ---------- Helpers de rutas ----------

def _bundle_base_dir() -> str:
    """Carpeta base para leer assets (p.ej., config) cuando está congelado."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS

    cwd_cfg = os.path.join(os.getcwd(), "config")
    if os.path.isdir(cwd_cfg):
        return os.getcwd()
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def _runtime_base_dir() -> str:
    return os.getcwd()

# ---------- Config ----------

def get_args():
    parser = argparse.ArgumentParser(description="Script para buscar un ScadaKey en Bases de Datos")
    parser.add_argument("empresa", type=str, help="Nombre de la empresa")
    parser.add_argument("keys", type=str, help="ScadaKeys separadas por comas")
    parser.add_argument("--dominio", type=str, default=None, help="Dominio (ej: CC, QA) para elegir carpeta SCADA")
    return parser.parse_args()

def get_config():
    base = _bundle_base_dir()
    config_path = os.path.join(base, "config", "buscar_key.json")
    if not os.path.isfile(config_path):
        alt = os.path.join(os.getcwd(), "config", "buscar_key.json")
        if os.path.isfile(alt):
            config_path = alt
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


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

def regex_from_pattern(pattern: str):
    patron_escapado = re.escape(pattern.strip().upper()).replace("%", ".")
    return f"^{patron_escapado}$"

# ---------- Main ----------

def main():
    args = get_args()
    empresa = args.empresa
    dominio = args.dominio
    keys = args.keys.split(",")  # Dividir las keys por comas

    # Bases de rutas
    runtime_base = _runtime_base_dir()  # donde escribimos
    bundle_base = _bundle_base_dir()    # de donde leemos config/assets (se usa en get_config)

    # Directorios de salida y log (siempre en runtime_base/CWD)
    out_root = os.path.join(runtime_base, "out")
    log_dir  = os.path.join(runtime_base, "log")
    topath   = os.path.join(out_root, "Find_key")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(topath, exist_ok=True)

    # Directorio donde están los CSV convertidos (out/<EMPRESA>/<SCADA|HSH|ODSTXT>)
    suffix = f"{dominio}SCADA" if dominio else "SCADA"
    directorio_empresa = os.path.join(out_root, empresa)

    # Inicializar LOG
    log_path = os.path.join(log_dir, "buscar_key.log")
    logger, logger_console = Logger.initlog(log_path)
    Logger.write_log().log_all("info", f"Inicio busqueda keys empresa {empresa}", logger_console, logger)

    # Cargar config
    config = get_config()
    Logger.write_log().log_all("info", "Configuracion de busqueda cargada", logger_console, logger)

    # DataFrame de resultados
    results = pd.DataFrame(columns=["Key", "DB", "Table", "Field", "Record"])

    # Normalizar claves a UPPER
    keys = [k.strip().upper() for k in keys]
    keys_encontradas = []

    # Recorrer carpetas de interés
    for folder in ["SCADA", "HSH", "ODSTXT"]:
        folder_name = suffix if folder == "SCADA" else folder
        folder_path = os.path.join(directorio_empresa, folder_name)
        Logger.write_log().log_all("info", f"Buscando en {folder}", logger_console, logger)

        if not os.path.exists(folder_path):
            # No existe esa subcarpeta; continúa
            continue

        for file in os.listdir(folder_path):
            if not file.endswith(".csv"):
                continue

            file_name = os.path.splitext(file)[0]
            if file_name not in config:
                continue

            nombres_columnas = config[file_name]

            # Lee CSV
            df = pd.read_csv(os.path.join(folder_path, file), dtype=str)
            table_name = file_name

            # Filtrado especial por nombre de archivo
            if file == "lookup_table.csv":
                df_filtrado = df.copy()
                df_filtrado[3] = df_filtrado[nombres_columnas[0]].str.split(".").str[0]
                df_filtrado = df_filtrado.iloc[:, [3, 0, 1]]

            elif file == "groups.csv":
                df_filtrado = df[nombres_columnas + ["CPID", "LinkAttributeValue"]]

            else:
                indices_columnas = [0] + [df.columns.get_loc(col) for col in nombres_columnas]
                df_filtrado = df.iloc[:, indices_columnas]
                df_filtrado = df_filtrado.dropna(subset=[df_filtrado.columns[0]])

            Logger.write_log().log_all(
                "info",
                f"Archivo {resolve_table_label(folder, table_name)} listo",
                logger_console,
                logger,
            )

            # Buscar claves
            for current_key in keys:
                regex = regex_from_pattern(current_key)
                for column in df_filtrado.columns:
                    found_rows = df_filtrado[
                        df_filtrado[column].astype(str).str.upper().str.contains(regex, regex=True, na=False)
                    ]
                    if found_rows.empty:
                        continue

                    if folder == "SCADA":
                        file_name_only = os.path.splitext(file)[0]
                        table_label = resolve_table_label(folder, file_name_only)
                        db_display, table_display = split_db_table_label(table_label)
                        if not db_display:
                            db_display = "SCADA"
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
                                logger_console,
                                logger,
                            )
                            keys_encontradas.append(key_encontrada)
                            resultado = pd.DataFrame(
                                {
                                    "Key": [key_encontrada],
                                    "DB": [db_display],
                                    "Table": [table_display],
                                    "Record": [record_value],
                                    "Field": [column],
                                }
                            )
                            results = pd.concat([results, resultado], ignore_index=True)

                    if folder == "ODSTXT":
                        for index in found_rows.index:
                            row = found_rows.loc[index]
                            full_row = df.loc[index]
                            file_name_only = os.path.splitext(file)[0]
                            table_label = resolve_table_label(folder, file_name_only)
                            unifilar_name_only = os.path.splitext(full_row.iloc[0])[0].split(".")[0]
                            key_encontrada = row[column]
                            nivel_tension = full_row.iloc[1]
                            location = full_row.iloc[5]
                            Logger.write_log().log_all(
                                "info",
                                f"Key {key_encontrada} coincide con {current_key} en {table_label} diagrama {unifilar_name_only} campo {column}",
                                logger_console,
                                logger,
                            )
                            keys_encontradas.append(key_encontrada)
                            resultado = pd.DataFrame(
                                {
                                    "Key": [key_encontrada],
                                    "DB": ["ODS"],
                                    "Table": [file_name_only],
                                    "Field": [unifilar_name_only],
                                    "NivelTension": [nivel_tension],
                                    "Location": [location],
                                }
                            )
                            results = pd.concat([results, resultado], ignore_index=True)

                    if folder == "HSH":
                        for _, row in found_rows.iterrows():
                            record = row[df_filtrado.columns[2]]
                            nombre_columna = df_filtrado.columns[2]
                            table = os.path.splitext(file)[0]
                            table_label = resolve_table_label(folder, table)
                            key_encontrada = row[column]
                            Logger.write_log().log_all(
                                "info",
                                f"Key {key_encontrada} coincide con {current_key} en {table_label} campo {nombre_columna} registro {record}",
                                logger_console,
                                logger,
                            )
                            keys_encontradas.append(key_encontrada)
                            resultado = pd.DataFrame(
                                {
                                    "Key": [key_encontrada],
                                    "DB": ["HSH"],
                                    "Table": [table],
                                    "Field": [nombre_columna],
                                    "Record": [record],
                                }
                            )
                            results = pd.concat([results, resultado], ignore_index=True)

    # Claves no encontradas
    claves_no_encontradas = list(set(keys) - set(keys_encontradas))
    for clave_no_encontrada in claves_no_encontradas:
        Logger.write_log().log_all("info", f"Key {clave_no_encontrada} sin resultados", logger_console, logger)
        resultado = pd.DataFrame({"Key": [clave_no_encontrada], "DB": ["NaN"], "Table": ["NaN"], "record": ["NaN"]})
        results = pd.concat([results, resultado], ignore_index=True)

    # Guardar Excel en topath (runtime/CWD/out/Find_key)
    ruta_excel = os.path.join(topath, name_file_out)
    results.to_excel(ruta_excel, index=False, header=True)

    # Post-procesar formato
    wb = openpyxl.load_workbook(ruta_excel)
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

    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions
    wb.save(ruta_excel)

    Logger.write_log().log_all("info", f"Archivo {name_file_out} creado", logger_console, logger)
    Logger.write_log().log_all("info", f"Keys con resultado {len(set(keys_encontradas))}", logger_console, logger)
    Logger.write_log().log_all("info", f"Keys sin resultado {len(claves_no_encontradas)}", logger_console, logger)
    Logger.write_log().log_all("info", "Busqueda de keys finalizada", logger_console, logger)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

