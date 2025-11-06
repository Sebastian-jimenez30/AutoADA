from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

from services.vault_service import VaultService
from services.server_resolver import ServerResolver
from utils.cli import build_cmd
from utils.data_checks import find_mode_data_ready

import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOADA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AutoADA"))
OUT_ROOT = os.path.join(AUTOADA_DIR, "out")
HSH_OUTPUT_DIR = os.path.join(OUT_ROOT, "HSH")

SERVER_RESOLVER = ServerResolver(os.path.join(AUTOADA_DIR, "config"))
SERVER_RESOLVER._path = os.path.join(AUTOADA_DIR, "config", "servers.json")

RESPALDO_MAP = {
    "ITCO": "TRA",
    "TRA": "ITCO",
    "REPS": "REPP",
    "REPP": "REPS",
}


@dataclass
class CrearResult:
    status: str
    message: str
    files: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


last_crear_result: Optional[CrearResult] = None


def get_empresas() -> Iterable[str]:
    return SERVER_RESOLVER.empresa_claves_view().keys()


def get_dominios() -> Iterable[str]:
    return SERVER_RESOLVER.opciones_dominio_view().keys()


def _run_subprocess_stream(
    cmd: list[str],
    label: str,
    env: dict[str, str],
    cwd: str,
) -> Generator[str, None, int]:
    yield f"\n--- {label} ---\n"
    yield f"$ {' '.join(cmd)}\n"
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
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


def _result_line(payload: dict[str, Any]) -> str:
    return f"RESULT::{json.dumps(payload, ensure_ascii=False)}\n"


def crear_tags_pipeline(
    empresa: str,
    dominio: str,
    archivo_path: str,
    archivo_nombre: str | None,
    aplicar: bool,
    forzar_actualizacion: bool,
) -> Generator[str, None, None]:
    global last_crear_result

    empresa = (empresa or "").strip().upper()
    dominio = (dominio or "").strip().upper() or "CC"
    archivo_nombre = archivo_nombre or os.path.basename(archivo_path)

    yield f"Iniciando proceso Crear Tag HSH para empresa={empresa} dominio={dominio} archivo={archivo_nombre}\n"

    def _store_result(status: str, message: str, files: list[str] | None = None, extra: dict[str, Any] | None = None):
        global last_crear_result
        last_crear_result = CrearResult(
            status=status,
            message=message,
            files=files or [],
            extra=extra or {},
        )

    if not empresa:
        payload = {"status": "ERROR", "message": "Debes seleccionar una empresa válida."}
        _store_result(payload["status"], payload["message"])
        yield _result_line(payload)
        return

    if not archivo_path or not os.path.isfile(archivo_path):
        payload = {"status": "ERROR", "message": "No se pudo acceder al archivo de entrada."}
        _store_result(payload["status"], payload["message"])
        yield _result_line(payload)
        return

    try:
        env = VaultService.build_env()
    except Exception as exc:
        yield f"Error obteniendo variables del vault: {exc}\n"
        message = "No se pudo construir el entorno. Verifica que el vault esté desbloqueado."
        _store_result("ERROR", message)
        yield _result_line({"status": "ERROR", "message": message})
        return

    respaldo = RESPALDO_MAP.get(empresa)
    servidor_principal = SERVER_RESOLVER.generar_server(empresa, dominio)
    if not servidor_principal:
        message = "No se pudo resolver el servidor principal para la empresa seleccionada."
        _store_result("ERROR", message)
        yield _result_line({"status": "ERROR", "message": message})
        return

    servidor_respaldo = SERVER_RESOLVER.generar_server(respaldo, dominio) if respaldo else None

    run_targets: list[tuple[str, Optional[str], str]] = [(empresa, respaldo, servidor_principal)]
    if aplicar and respaldo and servidor_respaldo:
        run_targets.append((respaldo, empresa, servidor_respaldo))

    ready, details = find_mode_data_ready(AUTOADA_DIR, empresa)
    needs_update = forzar_actualizacion or (not ready)
    yield f"Datos locales disponibles para {empresa}: {ready} (forzar={forzar_actualizacion})\n"
    yield f"Detalle OUT/SCADA/HSH/ODSTXT: {details}\n"

    report_paths: set[str] = set()
    info_paths: set[str] = set()
    extra_messages: list[str] = []

    def _collect_marker(line: str):
        nonlocal report_paths, info_paths, extra_messages
        if line.startswith("REPORT_PATH:"):
            report_paths.add(line.split(":", 1)[1].strip())
        elif line.startswith("INFO_PATH:"):
            info_paths.add(line.split(":", 1)[1].strip())
        elif line.startswith("QUERY_PATH:"):
            info_paths.add(line.split(":", 1)[1].strip())
        elif line.startswith("SUMMARY:"):
            extra_messages.append(line.split(":", 1)[1].strip())

    def _stream_script(label: str, cmd: list[str]) -> int:
        stream = _run_subprocess_stream(cmd, label, env=env, cwd=AUTOADA_DIR)
        rc: int | None = None
        try:
            while True:
                chunk = next(stream)
                if "[REPORT_PATH:" in chunk or "REPORT_PATH:" in chunk:
                    _collect_marker(chunk.split("[", 1)[-1] if "[" in chunk else chunk)
                elif "INFO_PATH:" in chunk or "QUERY_PATH:" in chunk or "SUMMARY:" in chunk:
                    _collect_marker(chunk.split("[", 1)[-1] if "[" in chunk else chunk)
                yield chunk
        except StopIteration as stop:
            rc = stop.value if isinstance(stop.value, int) else 0
        return rc if rc is not None else 0

    # Ejecución principal del script
    for target_empresa, target_respaldo, target_server in run_targets:
        accion = "Insertando" if aplicar else "Generando reporte"
        yield f"{accion} para empresa {target_empresa} (servidor {target_server})...\n"

        cmd = build_cmd("scripts.hsh_crear_tag", target_empresa, "--input", archivo_path)
        if target_respaldo:
            cmd += ["--respaldo", target_respaldo]
        if aplicar:
            cmd += ["--apply", "--server", target_server, "--skip-backup-insert"]

        rc = yield from _stream_script(f"CREAR-{target_empresa}", cmd)
        if rc != 0:
            message = f"El script hsh_crear_tag para {target_empresa} finalizó con errores (rc={rc})."
            files = sorted(report_paths | info_paths)
            _store_result("ERROR", message, files=files)
            yield _result_line({"status": "ERROR", "message": message, "files": files})
            return

    # Si se solicita actualización previa
    if needs_update:
        yield "Actualizando datasets SCADA/HSH antes de finalizar...\n"
        cmd_import = build_cmd("scripts.importar_all", servidor_principal, empresa, "sca,hsh", "--usecase", "hsh_crear_tag")
        rc_import = yield from _stream_script("IMPORT-HSH", cmd_import)
        if rc_import != 0:
            message = f"Importación previa falló (rc={rc_import})."
            files = sorted(report_paths | info_paths)
            _store_result("ERROR", message, files=files)
            yield _result_line({"status": "ERROR", "message": message, "files": files})
            return

        cmd_convert = build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "hsh")
        rc_convert = yield from _stream_script("CONVERT-HSH", cmd_convert)
        if rc_convert != 0:
            message = f"Conversión HSH falló (rc={rc_convert})."
            files = sorted(report_paths | info_paths)
            _store_result("ERROR", message, files=files)
            yield _result_line({"status": "ERROR", "message": message, "files": files})
            return

    files = sorted({os.path.normpath(p) for p in report_paths | info_paths if p})
    payload = {
        "status": "SUCCESS",
        "message": "Proceso de creación de tags completado.",
        "files": files,
        "details": extra_messages,
    }
    _store_result("SUCCESS", payload["message"], files=files, extra={"details": extra_messages})
    yield _result_line(payload)


def get_last_crear_result() -> CrearResult | None:
    return last_crear_result
