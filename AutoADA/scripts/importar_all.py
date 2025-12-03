# -*- coding: utf-8 -*-
import os
import sys
import argparse

from utils.paths import output_root

# Cargas tolerantes
try:
    from scripts import _Logger as Logger
    from scripts import import_scada, import_hsh, import_ods
except Exception:
    try:
        import _Logger as Logger
        import import_scada, import_hsh, import_ods
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger
        import import_scada, import_hsh, import_ods


def get_args():
    p = argparse.ArgumentParser(description='Orquestador de importaciones (SCADA/HSH/ODS) por usecase.')
    p.add_argument('hostname', type=str, help='Nombre del servidor')
    p.add_argument('empresa', type=str, help='Nombre de la empresa')
    p.add_argument('modo', type=str, help='Modos separados por coma: sca,hsh,ods')
    p.add_argument('--usecase', type=str, default=None, help='Nombre del usecase (ej: buscar_keys, hsh_validar, etc.)')
    p.add_argument('--flex', action='store_true', help='Importar también empresa relacionada (si aplica)')
    p.add_argument('--dominio', type=str, default=None, help='Dominio (ej: CC, QA) para segmentar SCADA')
    return p.parse_args()


def main():
    args = get_args()
    server = args.hostname
    empresa = args.empresa
    modo = args.modo
    usecase = args.usecase
    flex = bool(args.flex)
    dominio = args.dominio

    log_dir = os.path.join(output_root(), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "importar.log")
    logger, logger_console = Logger.initlog(log_path)

    acciones = {
        'sca': lambda: import_scada.run(server, empresa, usecase, flex, logger, logger_console, dominio=dominio),
        'hsh': lambda: import_hsh.run(server, empresa, usecase, flex, logger, logger_console),
        'ods': lambda: import_ods.run(server, empresa, usecase, flex, logger, logger_console),
    }

    for nombre in (x.strip() for x in modo.split(',')):
        fn = acciones.get(nombre)
        if fn:
            fn()
        else:
            Logger.write_log().log_all('warning', f'Modo desconocido: {nombre}', logger_console, logger)


if __name__ == "__main__":
    main()
