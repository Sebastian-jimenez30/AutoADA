# -*- coding: utf-8 -*-
import os
import sys
import time
from typing import Optional, Dict, Any

from utils.paths import input_root, output_root

# === IMPORTS TOLERANTES A PAQUETE/DATA ===
# import_base
try:
    from scripts.import_base import (
        load_profiles_config, resolve_usecase, make_target_dir, reset_dir,
        sftp_transfer, log_all, log_files, replace_server_prefix, related_company,
        related_server_candidates
    )
except Exception:
    try:
        from import_base import (
        load_profiles_config, resolve_usecase, make_target_dir, reset_dir,
        sftp_transfer, log_all, log_files, replace_server_prefix, related_company,
        related_server_candidates
        )
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        from import_base import (
        load_profiles_config, resolve_usecase, make_target_dir, reset_dir,
        sftp_transfer, log_all, log_files, replace_server_prefix, related_company,
        related_server_candidates
        )

# Logger + functions
try:
    from scripts import _Logger as Logger
    from scripts.functions import sshserver, scada_online
except Exception:
    try:
        import _Logger as Logger
        from functions import sshserver, scada_online
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger
        from functions import sshserver, scada_online


def run(server: str,
        empresa: str,
        usecase: Optional[str],
        flex: bool,
        logger,
        logger_console,
        evaluate_online: bool = True):
    """
    Importa SCADA:
      - Limpia *.dat en la carpeta remota ANTES del dump (si hay remote_cmd).
      - Ejecuta el dump remoto (segun usecase → remote_cmd).
      - Limpia/crea destino local input_root()/db/<empresa>/SCADA
      - SFTP: lista y transfiere archivos desde 'from_path'
      - Limpia *.dat en la carpeta remota DESPUES de la transferencia (si hay remote_cmd).
      - rm_fil.sh como refuerzo.
    Soporta 'flex' (empresa relacionada).
    """
    # ---- Resolver configuracion (dump/carpeta remota) segun usecase ----
    cfg = load_profiles_config()
    resolved = resolve_usecase(cfg, usecase)
    sc = resolved.get("scada", {}) or {}

    if not sc.get("enabled", False):
        log_all('info', f'SCADA deshabilitado para caso {usecase}', logger_console, logger)
        return

    remote_cmd = sc.get("remote_cmd")
    frompath   = sc.get("from_path") or "/opt/osi/osi_cust/data/pythondir/dbdump"

    # Logs clave de contexto
    log_all('info', f'Inicia importacion SCADA {empresa} ({usecase}) servidor {server}', logger_console, logger)
    if remote_cmd:
        log_all('info', 'Dump remoto habilitado', logger_console, logger)
        log_files('debug', f'Comando remoto SCADA {remote_cmd}', logger)
    else:
        log_all('info', 'Dump remoto omitido', logger_console, logger)
    log_all('info', f'Origen remoto {frompath}', logger_console, logger)

    # ---- Preparar destino local ----
    topath = os.path.join(input_root(), "db", empresa, "SCADA")
    os.makedirs(topath, exist_ok=True)

    try:
        if os.path.exists(topath) and os.listdir(topath):
            log_all('info', f'Reiniciando carpeta {topath}', logger_console, logger)
            import shutil
            shutil.rmtree(topath)
            time.sleep(1)
        os.makedirs(topath, exist_ok=True)
        log_all('info', f'Carpeta lista {topath}', logger_console, logger)
    except PermissionError as e:
        log_all('error', f'Fallo al reiniciar carpeta {topath}: {e}', logger_console, logger)
        return
    except Exception as e:
        log_all('error', f'Error inesperado al reiniciar carpeta {topath}: {e}', logger_console, logger)
        return

    # ---- Conexion SSH y verificacion de servidor ----
    client = sshserver(server, logger, logger_console)

    if evaluate_online:
        server_online = scada_online(client, logger, logger_console)
        if server_online != server:
            server = server_online
            log_all('info', f'Cambia a servidor SCADA {server}', logger_console, logger)
            client = sshserver(server, logger, logger_console)

    # ---- (Nuevo) Limpieza remota PRE-dump ----
    if remote_cmd:
        pre_clean_cmd = (
            f". /home/ada/.bash_profile ; "
            f"mkdir -p {frompath} ; "
            f"if command -v find >/dev/null 2>&1 ; then "
            f"  find {frompath} -maxdepth 1 -type f -name '*.dat' -delete ; "
            f"else "
            f"  cd {frompath} && rm -f *.dat ; "
            f"fi"
        )
        log_all('info', f'Prelimpieza remota {frompath}', logger_console, logger)
        stdin_c, stdout_c, stderr_c = client.exec_command(pre_clean_cmd)
        exit_clean = stdout_c.channel.recv_exit_status()
        if exit_clean == 0:
            log_all('info', f'Prelimpieza ok {frompath}', logger_console, logger)
        else:
            err = stderr_c.read().decode('utf-8', 'replace')
            log_all('warning', f'Prelimpieza fallo {frompath}', logger_console, logger)
            log_files('debug', err, logger)

    # ---- Ejecutar dump remoto ----
    if remote_cmd:
        log_all('info', f'Ejecuta dump remoto en {server}', logger_console, logger)
        log_files('debug', f'Comando dump SCADA {remote_cmd}', logger)
        stdin, stdout, stderr = client.exec_command(remote_cmd)

        while not stdout.channel.exit_status_ready():
            if stdout.channel.recv_ready():
                chunk = stdout.channel.recv(1024).decode('utf-8', errors='replace').strip()
                if chunk:
                    log_files('debug', chunk, logger)
            time.sleep(1)

        exit_status = stdout.channel.recv_exit_status()
        log_all('info', f'Dump remoto codigo {exit_status} en {server}', logger_console, logger)
        if exit_status != 0:
            error_message = stderr.read().decode('utf-8', errors='replace')
            log_all('error', f'Dump remoto fallo en {server}', logger_console, logger)
            log_files('debug', error_message, logger)

    # ---- Transferencia SFTP ----
    sftp_client = client.open_sftp()
    log_all('info', f'Listando SFTP {frompath}', logger_console, logger)
    dirlist = sftp_client.listdir(path=frompath)
    total_files = len(dirlist)

    for item in dirlist:
        log_files('debug', f'Ruta leida {frompath}/{item}', logger)
    log_all('info', f'Listado SFTP listo {frompath}', logger_console, logger)

    transferred_files = 0
    log_all('info', f'Inicio transferencia {frompath} -> {topath}', logger_console, logger)
    for file_name in dirlist:
        remote_file = f"{frompath}/{file_name}"  # POSIX
        try:
            sftp_client.get(remote_file, os.path.join(topath, file_name))
            log_files('debug', f'Archivo transferido {file_name}', logger)
            transferred_files += 1
        except Exception:
            log_all('warning', f'Fallo transferencia {file_name}', logger_console, logger)

    # Cerrar SFTP antes de limpiar remoto post-transferencia
    try:
        sftp_client.close()
    except Exception:
        pass

    # ---- Verificacion de transferencia ----
    if transferred_files == total_files:
        list_of_files = filter(lambda x: os.path.isfile(os.path.join(topath, x)), os.listdir(topath))
        files_with_size = [(file_name, os.stat(os.path.join(topath, file_name)).st_size) for file_name in list_of_files]
        for file_name, size in files_with_size:
            print(file_name, '-->', int(size / 1024), 'KB')
        log_all('info', f'Transferencia ok {transferred_files} archivos', logger_console, logger)
    else:
        log_all('error', f'Transferencia incompleta {transferred_files}/{total_files} archivos', logger_console, logger)

    # ---- (Nuevo) Limpieza remota POST-transfer ----
    if remote_cmd:
        post_clean_cmd = (
            f". /home/ada/.bash_profile ; "
            f"if command -v find >/dev/null 2>&1 ; then "
            f"  find {frompath} -maxdepth 1 -type f -name '*.dat' -delete ; "
            f"else "
            f"  cd {frompath} && rm -f *.dat ; "
            f"fi"
        )
        log_all('info', f'Postlimpieza remota {frompath}', logger_console, logger)
        stdin_pc, stdout_pc, stderr_pc = client.exec_command(post_clean_cmd)
        exit_post = stdout_pc.channel.recv_exit_status()
        if exit_post == 0:
            log_all('info', f'Postlimpieza ok {frompath}', logger_console, logger)
        else:
            err = stderr_pc.read().decode('utf-8', 'replace')
            log_all('warning', f'Postlimpieza fallo {frompath}', logger_console, logger)
            log_files('debug', err, logger)

    # ---- Refuerzo: rm_fil.sh (si existe) y cierre ----
    try:
        client.exec_command('/opt/osi/osi_cust/data/pythondir/scripts/rm_fil.sh')
    except Exception:
        pass
    try:
        client.close()
        log_files('debug', f'Conexion cerrada con servidor {server}', logger)
    except Exception:
        pass
    log_all('info', 'Importacion SCADA lista', logger_console, logger)

    # ---- FLEX (empresa relacionada) ----
    if flex:
        rel = related_company(empresa)
        if rel:
            candidates = related_server_candidates(server, empresa) or [replace_server_prefix(server, empresa)]
            last_error = None
            for server_rel in candidates:
                try:
                    log_all('info', f'Importacion SCADA flex {rel} via {server_rel}', logger_console, logger)
                    # Llamada recursiva sin flex para evitar bucle
                    run(server_rel, rel, usecase, False, logger, logger_console, evaluate_online=False)
                    break
                except Exception as exc:
                    last_error = exc
                    logger_console.exception(f"Error importacion SCADA flex para {rel} usando {server_rel}", exc_info=False)
                    logger.exception(exc, exc_info=True)
                    continue
            else:
                if last_error:
                    log_all('error', f'Importacion SCADA flex {rel} fallo en todos los candidatos', logger_console, logger)
