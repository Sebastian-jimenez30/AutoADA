# -*- coding: utf-8 -*-
import os
import sys

try:
    from scripts import _Logger as Logger
except Exception:
    try:
        import _Logger as Logger
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger


def display_by_domain(client, logger_console=None, logger=None) -> str:
    """
    Lee $OSIINET_DOMAIN y construye la ruta a display/.
    """
    stdin, stdout, stderr = client.exec_command('. /home/ada/.bash_profile ; echo $OSIINET_DOMAIN')
    domain = stdout.read().decode('ascii').strip("\n")
    path = f'/opt/osi/monarch/profiles/{domain}/NetworkFolders/System/display/'
    if logger_console and logger:
        Logger.write_log().log_all('info', f'Dominio OSI {domain} ruta display {path}', logger_console, logger)
    return path
