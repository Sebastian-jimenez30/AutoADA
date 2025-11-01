from __future__ import annotations

import json
import os
import subprocess
from typing import Generator, Iterable, Tuple

from services.vault_service import VaultService
from utils.cli import build_cmd
from utils.data_checks import find_mode_data_ready
from utils.paths import runtime_root

from services.server_resolver import ServerResolver

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOADA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AutoADA"))
SERVER_RESOLVER = ServerResolver(os.path.join(AUTOADA_DIR, "config"))
SERVER_RESOLVER._path = os.path.join(AUTOADA_DIR, "config", "servers.json")
RUNTIME_ROOT = runtime_root()


def get_empresas() -> Iterable[str]:
    return SERVER_RESOLVER.empresa_claves_view().keys()


def get_dominios() -> Iterable[str]:
    return SERVER_RESOLVER.opciones_dominio_view().keys()


def _validar_keys(cadena: str) -> Tuple[list[str], list[str]]:
    keys = [k.strip().upper() for k in (cadena or "").split(",") if k.strip()]
    validas, invalidas = [], []
    for key in keys:
        if "%" in key:
            validas.append(key)
        elif len(key) == 8 and key[:5].isdigit() and key[6:].isdigit():
            validas.append(key)
        else:
            invalidas.append(key)
    return validas, invalidas


def _result_line(status: str, message: str, path: str | None = None) -> str:
    payload = {"status": status, "message": message}
    if path:
        payload["path"] = path
    return f"RESULT::{json.dumps(payload, ensure_ascii=False)}\n"


def _run_subprocess_stream(cmd: list[str], label: str, env: dict[str, str]) -> Generator[str, None, int]:
    yield f"\n--- {label} ---\n"
    yield f"$ {' '.join(cmd)}\n"
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=AUTOADA_DIR,
        env=env,
    )

    try:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            if line:
                yield f"[{label}] {line}\n"
    finally:
        try:
            if process.stdout:
                process.stdout.close()
        except Exception:
            pass

    rc = process.wait()
    yield f"[{label}] Código de salida: {rc}\n"
    return rc


def buscar_key_pipeline(
    empresa: str,
    dominio: str,
    keys: str,
    forzar_actualizacion: bool,
) -> Generator[str, None, None]:
    empresa = (empresa or "").strip().upper()
    dominio = (dominio or "").strip().upper()
    yield f"Iniciando búsqueda de keys para empresa={empresa} dominio={dominio}\n"

    if not empresa:
        yield _result_line("ERROR", "Debes seleccionar una empresa válida.")
        return
    if not dominio:
        yield _result_line("ERROR", "Debes seleccionar un dominio válido.")
        return

    keys_validas, keys_invalidas = _validar_keys(keys)
    if keys_invalidas:
        yield f"Keys inválidas detectadas: {', '.join(keys_invalidas)}\n"
    if not keys_validas:
        yield _result_line("ERROR", "No hay keys válidas para procesar.")
        return

    try:
        env = VaultService.build_env()
    except Exception as exc:  # pragma: no cover
        yield f"Error cargando variables del vault: {exc}\n"
        yield _result_line("ERROR", "No se pudo construir el entorno. Verifica que el vault esté desbloqueado.")
        return

    ready, details = find_mode_data_ready(None, empresa)
    needs_update = forzar_actualizacion or (not ready)
    yield f"Datos locales disponibles: {ready} (forzar={forzar_actualizacion})\n"
    yield f"Detalle OUT/SCADA/HSH/ODSTXT: {details}\n"

    usecase = "buscar_keys"

    def _abort(message: str):
        yield message + "\n"
        yield _result_line("ERROR", message)

    if not needs_update:
        cmd = build_cmd("scripts.buscar_key", empresa, ",".join(keys_validas))
        rc = yield from _run_subprocess_stream(cmd, "BUSCAR", env)
        if rc == 0:
            output_file = os.path.join(RUNTIME_ROOT, "out", "Find_key", "Find_Key.xlsx")
            msg = (
                f"Búsqueda completada exitosamente. "
                f"Archivo esperado en: {output_file}"
            )
            yield _result_line("SUCCESS", msg, output_file)
        else:
            yield _result_line("ERROR", "El comando de búsqueda finalizó con errores.")
        return

    servidor = SERVER_RESOLVER.generar_server(empresa, dominio)
    if not servidor:
        yield from _abort("No se pudo resolver el servidor para la empresa y dominio seleccionados.")
        return

    yield f"Actualizando datos desde el servidor '{servidor}' antes de buscar.\n"

    steps = [
        ("IMPORT-SCA", build_cmd("scripts.importar_all", servidor, empresa, "sca", "--usecase", usecase)),
        ("CONVERT-SCA", build_cmd("scripts.Convertir_all", empresa, "Buscar_keys", "--only", "sca")),
        ("IMPORT-HSH", build_cmd("scripts.importar_all", servidor, empresa, "hsh", "--usecase", usecase)),
        ("CONVERT-HSH", build_cmd("scripts.Convertir_all", empresa, "Buscar_keys", "--only", "hsh")),
        ("IMPORT-ODS", build_cmd("scripts.importar_all", servidor, empresa, "ods", "--usecase", usecase)),
        ("CONVERT-ODS", build_cmd("scripts.Convertir_all", empresa, "Buscar_keys", "--only", "ods")),
        ("CONVERT-ODS_CSV", build_cmd("scripts.Convertir_all", empresa, "Buscar_keys", "--only", "ods_csv")),
    ]

    for label, cmd in steps:
        rc = yield from _run_subprocess_stream(cmd, label, env)
        if rc != 0:
            yield from _abort(f"El paso {label} finalizó con errores (rc={rc}).")
            return

    cmd_buscar = build_cmd("scripts.buscar_key", empresa, ",".join(keys_validas))
    rc_buscar = yield from _run_subprocess_stream(cmd_buscar, "BUSCAR", env)
    if rc_buscar == 0:
        output_file = os.path.join(RUNTIME_ROOT, "out", "Find_key", "Find_Key.xlsx")
        msg = (
            "Búsqueda completada exitosamente tras la actualización. "
            f"Archivo generado en: {output_file}"
        )
        yield _result_line("SUCCESS", msg, output_file)
    else:
        yield _result_line("ERROR", "El comando de búsqueda finalizó con errores.")
