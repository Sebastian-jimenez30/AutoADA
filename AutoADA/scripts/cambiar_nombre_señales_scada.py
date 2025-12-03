#!/usr/bin/env python3
"""
cambiar_nombre_senales_scada.py
===============================
Módulo para cambiar nombre/descripción de senales SCADA usando formato dbset-k.
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Dict, Set, Tuple

import pandas as pd
import warnings

# Suprimir warnings innecesarios
warnings.simplefilter('ignore')

# Importar logger con manejo de errores robusto
try:
    from scripts import _Logger as Logger
except ImportError:
    try:
        import _Logger as Logger
    except ImportError:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger

# Configuración global
REQUIRED_COLUMNS = ["SCADA KEY", "DESCRIPCIÓN", "DESCRIPCIÓN NUEVA"]
MAX_DESCRIPTION_LENGTH = 64
SCADA_TYPES = {4: "STATUS", 5: "ANALOG"}
CSV_ENCODING = 'ISO-8859-1'
EXCEL_ENCODING = 'utf-8'


def _scada_path(root: Path, empresa: str, dominio: str | None = None) -> Path:
    """Ruta a SCADA según dominio (default SCADA)."""
    suffix = f"{dominio}SCADA" if dominio else "SCADA"
    return root / "out" / empresa / suffix


def get_args() -> argparse.Namespace:
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description='Cambiar nombre/descripción de senales SCADA.')
    parser.add_argument('archivo_excel', help='Archivo Excel de entrada')
    parser.add_argument('empresa', help='Nombre de la empresa')
    parser.add_argument('--dominio', type=str, default=None, help='Dominio (ej: CC, QA) para elegir carpeta SCADA')
    
    args = parser.parse_args()
    if not os.path.exists(args.archivo_excel):
        raise FileNotFoundError(f"Archivo Excel no encontrado: {args.archivo_excel}")
    
    return args


def setup_directories(empresa: str, dominio: str | None = None) -> Tuple[Path, Path, Path]:
    """Configura y crea directorios necesarios."""
    root = Path(os.getcwd())
    output_dir = root / "out" / "Name"
    log_dir = root / "log"
    scada_dir = _scada_path(root, empresa, dominio)

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    return output_dir, log_dir, scada_dir


def format_key_list(keys: list, max_display: int = 10) -> str:
    """Formatea lista de claves para mostrar en logs."""
    if not keys:
        return "[]"
    
    if len(keys) <= max_display:
        return f"[{', '.join(map(str, keys))}]"
    else:
        return f"[{', '.join(map(str, keys[:max_display]))}... y {len(keys) - max_display} mas]"


def load_excel_data(excel_path: str, logger: object, logger_console: object) -> pd.DataFrame:
    """Carga datos desde Excel con validaciones básicas."""
    try:
        df = pd.read_excel(excel_path, sheet_name="CAMBIO SCADA", dtype={'SCADA KEY': str})
        
        if df.empty:
            Logger.write_log().log_all("warning", "Hoja CAMBIO SCADA vacia", logger_console, logger)
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        
        # Normalizar y limpiar datos
        for col in REQUIRED_COLUMNS:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str).str.strip()
        
        # Eliminar duplicados
        duplicados = df['SCADA KEY'].duplicated(keep='first')
        if duplicados.any():
            Logger.write_log().log_all("warning", 
                f"Eliminados {duplicados.sum()} duplicados: {format_key_list(df[duplicados]['SCADA KEY'].tolist())}", 
                logger_console, logger)
        
        df = df.drop_duplicates(subset=['SCADA KEY'], keep='first')
        Logger.write_log().log_all("info", f"Excel cargado {len(df)} registros", logger_console, logger)
        return df
        
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al cargar Excel: {e}", logger_console, logger)
        return pd.DataFrame(columns=REQUIRED_COLUMNS)


def load_scada_files(scada_dir: Path, logger: object, logger_console: object) -> Dict[int, pd.DataFrame]:
    """Carga archivos SCADA CSV."""
    scada_data = {}
    scada_files = {4: scada_dir / "10_4.csv", 5: scada_dir / "10_5.csv"}
    
    for tipo, file_path in scada_files.items():
        try:
            if file_path.exists():
                df = pd.read_csv(file_path, encoding=CSV_ENCODING, 
                                low_memory=False, usecols=['Key', '#record'])
                scada_data[tipo] = df
                Logger.write_log().log_all("info", f"Archivo SCADA 10_{tipo} cargado", logger_console, logger)
            else:
                Logger.write_log().log_all("warning", f"Archivo SCADA no encontrado: {file_path}", logger_console, logger)
                scada_data[tipo] = pd.DataFrame(columns=['Key', '#record'])
        except Exception as e:
            Logger.write_log().log_all("error", f"Error al cargar {file_path}: {e}", logger_console, logger)
            scada_data[tipo] = pd.DataFrame(columns=['Key', '#record'])
    
    return scada_data


def create_scada_dictionary(scada_dir: Path, logger: object, logger_console: object) -> Dict[str, str]:
    """Crea diccionario de senales SCADA para validaciones."""
    try:
        df_list = []
        for tipo in [4, 5]:
            file_path = scada_dir / f"10_{tipo}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path, encoding=EXCEL_ENCODING, 
                               low_memory=False, usecols=['Key', 'Name'])
                df_list.append(df)
        
        if df_list:
            df_combined = pd.concat(df_list, ignore_index=True).drop_duplicates(subset='Key', keep='first')
            return dict(zip(df_combined['Key'], df_combined['Name']))
        else:
            Logger.write_log().log_all("warning", "No se cargaron archivos para diccionario SCADA", logger_console, logger)
            return {}
            
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al crear diccionario SCADA: {e}", logger_console, logger)
        return {}


def validate_and_filter(df: pd.DataFrame, scada_dir: Path, logger: object, logger_console: object) -> pd.DataFrame:
    """Valida y filtra datos"""
    if df.empty:
        return df
    
    initial_count = len(df)
    scada_dict = create_scada_dictionary(scada_dir, logger, logger_console)
    
    # Filtrar descripciones demasiado largas
    long_desc_mask = df['DESCRIPCIÓN NUEVA'].str.len() > MAX_DESCRIPTION_LENGTH
    if long_desc_mask.any():
        Logger.write_log().log_all("warning", 
            f"No se procesaran {long_desc_mask.sum()} senales por descripciones > {MAX_DESCRIPTION_LENGTH} chars: "
            f"{format_key_list(df[long_desc_mask]['SCADA KEY'].tolist())}", 
            logger_console, logger)
        df = df[~long_desc_mask]
    
    # Añadir nombres actuales y filtrar descripciones idénticas
    df['Name_Actual'] = df['SCADA KEY'].map(scada_dict)
    identical_mask = (df['Name_Actual'].notna()) & (df['DESCRIPCIÓN NUEVA'] == df['Name_Actual'])
    if identical_mask.any():
        Logger.write_log().log_all("warning", 
            f"No se procesaran {identical_mask.sum()} senales por descripciones identicas: "
            f"{format_key_list(df[identical_mask]['SCADA KEY'].tolist())}",
            logger_console, logger)
        df = df[~identical_mask]
    
    # Filtrar senales no encontradas
    not_found_mask = df['Name_Actual'].isna()
    if not_found_mask.any():
        Logger.write_log().log_all("warning", 
            f"No se procesaran {not_found_mask.sum()} senales no encontradas en SCADA: "
            f"{format_key_list(df[not_found_mask]['SCADA KEY'].tolist())}",
            logger_console, logger)
        df = df[~not_found_mask]
    
    Logger.write_log().log_all("info", f"Validacion: {len(df)} registros validos de {initial_count}", logger_console, logger)
    return df.drop(columns=['Name_Actual'])


def process_for_output(df: pd.DataFrame, scada_dir: Path, logger: object, logger_console: object) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Procesa datos para generar archivos de salida."""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    scada_data = load_scada_files(scada_dir, logger, logger_console)
    
    # Preparar datos combinados
    combined_scada = []
    for tipo, scada_df in scada_data.items():
        if not scada_df.empty:
            scada_df = scada_df.copy()
            scada_df['tipo'] = tipo
            combined_scada.append(scada_df)
    
    if not combined_scada:
        Logger.write_log().log_all("error", "No hay datos SCADA disponibles", logger_console, logger)
        return pd.DataFrame(), pd.DataFrame()
    
    df_scada = pd.concat(combined_scada, ignore_index=True)
    df_result = df.merge(df_scada, left_on='SCADA KEY', right_on='Key', how='left')
    
    # Verificar senales sin correspondencia
    no_match = df_result['tipo'].isna()
    if no_match.any():
        Logger.write_log().log_all("warning", 
            f"Senales sin correspondencia en SCADA: {format_key_list(df_result[no_match]['SCADA KEY'].tolist())}", 
            logger_console, logger)
    
    # Procesar cada tipo de señal
    results = {}
    for tipo in SCADA_TYPES:
        tipo_data = df_result[df_result['tipo'] == tipo].copy()
        if not tipo_data.empty:
            tipo_name = SCADA_TYPES[tipo]
            tipo_data['#record'] = tipo_data['#record'].astype(int)
            tipo_data[str(tipo)] = None
            tipo_data[tipo_name] = None
            
            # Columnas finales y renombrar
            final_cols = [str(tipo), tipo_name, '#record', 'Key', 'DESCRIPCIÓN NUEVA']
            tipo_data = tipo_data[final_cols].rename(columns={'DESCRIPCIÓN NUEVA': 'Name'})
            
            results[tipo] = tipo_data
            Logger.write_log().log_all("info", f"Procesadas {len(tipo_data)} senales {tipo_name.lower()}", 
                                      logger_console, logger)
        else:
            results[tipo] = pd.DataFrame()
    
    return results.get(4, pd.DataFrame()), results.get(5, pd.DataFrame())


def get_scada_keys(scada_dir: Path, logger: object, logger_console: object) -> Tuple[Set[str], Set[str]]:
    """Obtiene conjuntos de claves para senales status y analog."""
    status_keys = set()
    analog_keys = set()
    
    try:
        for tipo, keys_set in [(4, status_keys), (5, analog_keys)]:
            file_path = scada_dir / f"10_{tipo}.csv"
            if file_path.exists():
                df = pd.read_csv(file_path, encoding=CSV_ENCODING, low_memory=False, usecols=['Key'])
                keys_set.update(df['Key'].astype(str).str.strip())
    except Exception as e:
        Logger.write_log().log_all("warning", f"Error al cargar archivos para claves: {e}", logger_console, logger)
    
    return status_keys, analog_keys


def write_change_key_file(df: pd.DataFrame, output_path: Path, scada_dir: Path, logger: object, logger_console: object) -> None:
    """Escribe archivo de cambio de claves en formato dbset-k."""
    if df is None or df.empty:
        Logger.write_log().log_all("warning", "DataFrame vacio, no se creara archivo change_key", logger_console, logger)
        return
    
    # Filtrar datos válidos
    df_clean = df[(df['SCADA KEY'].notna() & df['SCADA KEY'] != '') & 
                  (df['DESCRIPCIÓN NUEVA'].notna() & df['DESCRIPCIÓN NUEVA'] != '')]
    
    if df_clean.empty:
        Logger.write_log().log_all("warning", "No hay datos validos para archivo change_key", logger_console, logger)
        return
    
    # Obtener claves por tipo
    status_keys, analog_keys = get_scada_keys(scada_dir, logger, logger_console)
    
    # Preparar comandos dbset-k
    output_data = []
    counts = {'status': 0, 'analog': 0, 'unknown': 0}
    
    for _, row in df_clean.iterrows():
        key = str(row['SCADA KEY']).strip()
        desc = row["DESCRIPCIÓN NUEVA"]
        
        if key in status_keys:
            # Status: usar 10 4 4
            output_data.append(f'dbset-k 10 4 4 {key} 0 = "{desc}"')
            counts['status'] += 1
        elif key in analog_keys:
            # Analog: usar 10 5 4
            output_data.append(f'dbset-k 10 5 4 {key} 0 = "{desc}"')
            counts['analog'] += 1
        else:
            # Tipo desconocido: intentar con ambos formatos
            output_data.append(f'dbset-k 10 4 4 {key} 0 = "{desc}"')
            output_data.append(f'dbset-k 10 5 4 {key} 0 = "{desc}"')
            counts['unknown'] += 1
            Logger.write_log().log_all("warning", f"Tipo desconocido para key {key}, se generan dos comandos", 
                                      logger_console, logger)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_data))
        
        Logger.write_log().log_all("info", f"Archivo change_key guardado: {output_path}", logger_console, logger)
        Logger.write_log().log_all("info", f"Resumen: {counts['status']} status, {counts['analog']} analog, {counts['unknown']} sin_tipo", 
                                  logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al escribir {output_path}: {e}", logger_console, logger)


def write_scada_changes_file(df_status: pd.DataFrame, df_analog: pd.DataFrame, output_path: Path, 
                            logger: object, logger_console: object) -> None:
    """Escribe archivo de cambios SCADA."""
    if (df_status.empty and df_analog.empty):
        Logger.write_log().log_all("warning", "DataFrames vacios, no se guarda archivo SCADA", logger_console, logger)
        return
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            f.write("10,SCADA.DB\n")
            
            if not df_status.empty:
                df_status.to_csv(f, index=False, quoting=csv.QUOTE_NONE)
                f.write("0\n")
            
            if not df_analog.empty:
                if not df_status.empty:
                    f.write("*\n")
                df_analog.to_csv(f, index=False, quoting=csv.QUOTE_NONE)
                f.write("0\n")
            
            f.write("0")
        
        Logger.write_log().log_all("info", f"Archivo cambios SCADA guardado: {output_path}", logger_console, logger)
    except Exception as e:
        Logger.write_log().log_all("error", f"Error al escribir {output_path}: {e}", logger_console, logger)


def main():
    """Función principal del proceso."""
    try:
        # Configuración inicial
        args = get_args()
        archivo_excel = args.archivo_excel
        empresa = args.empresa
        dominio = getattr(args, "dominio", None)
        output_dir, log_dir, scada_dir = setup_directories(empresa, dominio)
        
        # Inicializar logger
        logger, logger_console = Logger.initlog(log_dir / "cambiar_nombre_senales.log")
        Logger.write_log().log_all("info", "=== Inicio cambio senales SCADA ===", logger_console, logger)
        
        # Validar directorio SCADA
        if not scada_dir.exists():
            Logger.write_log().log_all("error", f"Directorio SCADA no encontrado: {scada_dir}", logger_console, logger)
            return False
        
        # Cargar y procesar datos
        df_raw = load_excel_data(archivo_excel, logger, logger_console)
        if df_raw.empty:
            Logger.write_log().log_all("warning", "No hay datos para procesar", logger_console, logger)
            return False
        
        df_validated = validate_and_filter(df_raw, scada_dir, logger, logger_console)
        if df_validated.empty:
            Logger.write_log().log_all("warning", "No hay datos validos despues de validaciones", logger_console, logger)
            return False
        
        # Generar archivos de salida
        write_change_key_file(df_validated, output_dir / 'change_key.csv', scada_dir, logger, logger_console)
        
        df_status, df_analog = process_for_output(df_validated, scada_dir, logger, logger_console)
        write_scada_changes_file(df_status, df_analog, output_dir / 'cambiar_nombre_senales.csv', 
                               logger, logger_console)
        
        Logger.write_log().log_all("info", "=== Proceso completado ===", logger_console, logger)
        return True
        
    except Exception as e:
        Logger.write_log().log_all("error", f"Error en proceso principal: {e}", logger_console, logger)
        return False


if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except KeyboardInterrupt:
        # Manejo básico de interrupción
        print("Proceso interrumpido por el usuario")
        sys.exit(2)
    except Exception as e:
        print(f"Error crítico: {e}")
        sys.exit(1)
