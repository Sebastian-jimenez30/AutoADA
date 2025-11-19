"""Eliminar señales SCADA (STATUS/ANALOG) + export de controles.

Versión sin acentos para uso en ejecutable (PyInstaller).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import warnings

import pandas as pd

try:
    from scripts import _Logger as Logger  # type: ignore
except Exception:
    try:
        import _Logger as Logger  # type: ignore
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger  # type: ignore


warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def _rt() -> str:
    return os.getcwd()


ROOT = _rt()
CARPETA_SALIDA = os.path.join(ROOT, "out", "Delete")
os.makedirs(CARPETA_SALIDA, exist_ok=True)

CARPETA_LOG = os.path.join(ROOT, "log")
os.makedirs(CARPETA_LOG, exist_ok=True)

log_path = os.path.join(CARPETA_LOG, "eliminar_senales.log")
logger, logger_console = Logger.initlog(log_path)


def get_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eliminar señales SCADA (STATUS/ANALOG).")
    p.add_argument("archivo_excel", type=str, help="Archivo Excel de entrada")
    p.add_argument("empresa", type=str, help="Nombre de la empresa")
    return p.parse_args()


def cargar_datos_eliminar(archivo_excel: str, empresa: str):
    try:
        try:
            delete = pd.read_excel(
                archivo_excel,
                sheet_name="CAMBIO ELIMINAR",
                dtype={"SCADA KEY": str},
            )
        except Exception as e:
            Logger.write_log().log_all(
                "warning",
                f"No se encontró la hoja 'CAMBIO ELIMINAR': {e}",
                logger_console,
                logger,
            )
            delete = pd.DataFrame(columns=["SCADA KEY", "DESCRIPCION"])

        if not delete.empty and "SCADA KEY" in delete.columns:
            duplicados = delete[delete["SCADA KEY"].duplicated(keep=False)]
            if not duplicados.empty:
                Logger.write_log().log_all(
                    "warning",
                    f"Keys duplicadas en 'CAMBIO ELIMINAR': {duplicados['SCADA KEY'].tolist()}",
                    logger_console,
                    logger,
                )
                delete.drop_duplicates(subset=["SCADA KEY"], keep="first", inplace=True)

        ruta_scada = os.path.join(ROOT, "out", empresa, "SCADA")

        scada_status_df = pd.read_csv(
            os.path.join(ruta_scada, "10_4.csv"),
            encoding="ISO-8859-1",
            low_memory=False,
            usecols=["Key", "ICaddress", "Name"],
        )
        scada_analog_df = pd.read_csv(
            os.path.join(ruta_scada, "10_5.csv"),
            encoding="ISO-8859-1",
            low_memory=False,
            usecols=["Key", "ICaddress", "Name"],
        )
        controls_df = pd.read_csv(
            os.path.join(ruta_scada, "32_20.csv"),
            encoding="ISO-8859-1",
            low_memory=False,
            usecols=["SourceKey", "GuidAsString"],
        )

        scada_status_keys = set(scada_status_df["Key"].dropna().astype(str))
        scada_analog_keys = set(scada_analog_df["Key"].dropna().astype(str))

        Logger.write_log().log_all(
            "info", "Archivos SCADA cargados correctamente.", logger_console, logger
        )
        return delete, scada_status_keys, scada_analog_keys, controls_df
    except Exception as e:
        Logger.write_log().log_all(
            "error", f"Error al cargar archivos: {e}", logger_console, logger
        )
        return None, None, None, None


def asignar_status_analog(key, scada_status, scada_analog):
    key = str(key).strip().upper()
    if key in scada_status:
        return "STATUS"
    if key in scada_analog:
        return "ANALOG"
    return key


def generar_archivos(delete_df, scada_status_keys, scada_analog_keys, controls_df):
    out_delete = os.path.join(CARPETA_SALIDA, "Delete_Keys.csv")
    out_controls = os.path.join(CARPETA_SALIDA, "Delete_Controls.csv")

    delete_df["SCADA KEY"] = delete_df["SCADA KEY"].astype(str).str.strip().str.upper()
    delete_df["Tipo"] = delete_df["SCADA KEY"].apply(
        lambda k: asignar_status_analog(k, scada_status_keys, scada_analog_keys)
    )

    keys_eliminar = delete_df["SCADA KEY"].tolist()

    with open(out_delete, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Key", "Tipo"])
        for _, row in delete_df.iterrows():
            writer.writerow([row["SCADA KEY"], row["Tipo"]])

    controls_filtrados = controls_df[controls_df["SourceKey"].isin(keys_eliminar)]
    controls_filtrados.to_csv(out_controls, index=False, sep=";")

    Logger.write_log().log_all(
        "info",
        f"Archivos de eliminación generados en {CARPETA_SALIDA}",
        logger_console,
        logger,
    )


def main() -> None:
    args = get_args()
    delete_df, s_status, s_analog, controls_df = cargar_datos_eliminar(
        args.archivo_excel, args.empresa
    )
    if delete_df is None:
        sys.exit(1)
    generar_archivos(delete_df, s_status, s_analog, controls_df)


if __name__ == "__main__":
    main()

