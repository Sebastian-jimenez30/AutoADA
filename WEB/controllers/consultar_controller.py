from __future__ import annotations

import csv
import json
import os
import socket
import sys
from dataclasses import dataclass, field
from typing import Any, Generator, List, Optional

from services.vault_service import VaultService
from services.server_resolver import ServerResolver
from utils.cli import build_cmd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUX_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
AUTOADA_DIR = os.path.join(AUX_ROOT, "AutoADA")
OUT_ROOT = os.path.join(AUTOADA_DIR, "out")

if AUTOADA_DIR not in sys.path:
    sys.path.insert(0, AUTOADA_DIR)

SERVER_RESOLVER = ServerResolver(os.path.join(AUTOADA_DIR, "config"))
SERVER_RESOLVER._path = os.path.join(AUTOADA_DIR, "config", "servers.json")


@dataclass
class ConsultarResult:
    status: str
    message: str
    files: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


last_consultar_rtu_result: Optional[ConsultarResult] = None
last_empresas_cache: Optional[list[str]] = None


def _summary_line(message: str, variant: str = "info") -> str:
    return f"SUMMARY::{message}|{variant}\n"


def _result_line(payload: dict[str, Any]) -> str:
    return f"RESULT::{json.dumps(payload, ensure_ascii=False)}\n"


def get_empresas() -> list[str]:
    # Similar a otros detectores: ITCO/TRA en hosts itco/tra, REPS/REPP en rep
    try:
        host = socket.gethostname().lower()
        if host.startswith(("itco1", "tra1", "isa1cct5_p", "desktop-n14qm43", "isa1ccwx_p")):
            return ["ITCO", "TRA"]
        if host.startswith(("rep1", "rep2")):
            return ["REPS", "REPP"]
    except Exception:
        pass
    return ["ITCO", "TRA"]


def _run_subprocess_stream(cmd: list[str], label: str, env: dict[str, str], cwd: str) -> Generator[str, None, int]:
    yield f"\n--- {label} ---\n"
    yield f"$ {' '.join(cmd)}\n"
    import subprocess

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env,
    )
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            if line:
                yield f"[{label}] {line}\n"
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
    rc = proc.wait()
    yield f"[{label}] Código de salida: {rc}\n"
    return rc


def actualizar_rtu_dataset(empresa: str) -> Generator[str, None, None]:
    """Importa/convierte SCADA (perfil default, solo SCADA) para consultar RTU."""
    empresa = (empresa or "").strip().upper()
    dominio = "CC"
    try:
        env = VaultService.build_env()
    except Exception as exc:
        yield _result_line({"status": "ERROR", "message": f"No se pudo construir el entorno: {exc}"})
        return

    servidor = SERVER_RESOLVER.generar_server(empresa, dominio)
    if not servidor:
        yield _result_line({"status": "ERROR", "message": "No se pudo resolver el servidor para la empresa seleccionada."})
        return

    cmd_import = build_cmd("scripts.importar_all", servidor, empresa, "sca", "--usecase", "default")
    rc_import = yield from _run_subprocess_stream(cmd_import, "IMPORT-SCADA", env, AUTOADA_DIR)
    if rc_import != 0:
        yield _result_line({"status": "ERROR", "message": f"Importación SCADA falló (rc={rc_import})."})
        return

    cmd_convert = build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "sca")
    rc_convert = yield from _run_subprocess_stream(cmd_convert, "CONVERT-SCADA", env, AUTOADA_DIR)
    if rc_convert != 0:
        yield _result_line({"status": "ERROR", "message": f"Conversión SCADA falló (rc={rc_convert})."})
        return

    yield _result_line({"status": "SUCCESS", "message": "Datos SCADA actualizados."})


def load_rtus(empresa: str, search: str | None = None, limit: int = 500) -> dict[str, Any]:
    """Lee RTUs/SAS desde SCADA (32_6.csv) y devuelve lista para UI."""
    empresa = (empresa or "").strip().upper()
    scada_dir = os.path.join(OUT_ROOT, empresa, "SCADA")
    file_path = os.path.join(scada_dir, "32_6.csv")
    items: list[str] = []
    if not os.path.isfile(file_path):
        return {"empresa": empresa, "count": 0, "rtus": []}
    try:
        with open(file_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rtu = row.get("RTU/SAS") or row.get("RTU") or row.get("#record") or ""
                name = row.get("Name") or row.get("Nombre") or ""
                if not rtu:
                    continue
                label = f"{rtu}: {name}".strip()
                items.append(label)
    except Exception:
        return {"empresa": empresa, "count": 0, "rtus": []}

    # de-dup
    seen = set()
    uniq: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            uniq.append(it)

    if search:
        s = search.strip().lower()
        uniq = [u for u in uniq if s in u.lower()]

    return {"empresa": empresa, "count": len(uniq), "rtus": uniq[:limit], "has_more": len(uniq) > limit}


def consultar_rtu_pipeline(empresa: str, selected_rtus: list[str]) -> Generator[str, None, None]:
    """Ejecuta scripts.consultar_rtu con la lista seleccionada."""
    global last_consultar_rtu_result
    last_consultar_rtu_result = None
    empresa = (empresa or "").strip().upper()
    if not empresa:
        yield _result_line({"status": "ERROR", "message": "Debes seleccionar una empresa."})
        return
    if not selected_rtus:
        yield _result_line({"status": "ERROR", "message": "Selecciona al menos una RTU/SAS."})
        return

    try:
        env = VaultService.build_env()
    except Exception as exc:
        yield _result_line({"status": "ERROR", "message": f"No se pudo construir el entorno: {exc}"})
        return

    rtus_arg = ", ".join(selected_rtus)
    cmd = build_cmd("scripts.consultar_rtu", "--empresa", empresa, "--rtus", rtus_arg)
    report_holder: dict[str, str | None] = {"path": None}

    stream = _run_subprocess_stream(cmd, "CONSULTAR-RTU", env, AUTOADA_DIR)
    rc: int | None = None
    try:
        while True:
            chunk = next(stream)
            line = chunk.strip()
            if line.startswith("[CONSULTAR-RTU]") and "RTU_REPORT:" in line:
                try:
                    _, payload = line.split("RTU_REPORT:", 1)
                    report_holder["path"] = payload.strip()
                except Exception:
                    pass
            yield chunk
    except StopIteration as stop:
        rc = stop.value if isinstance(stop.value, int) else 0

    status = "SUCCESS" if rc == 0 else "ERROR"
    message = "Consulta RTU lista" if rc == 0 else "Consulta RTU terminó con errores."
    files: list[str] = []
    if report_holder.get("path"):
        p = report_holder["path"]
        if p and not os.path.isabs(p):
            p = os.path.join(AUTOADA_DIR, p)
        if p and os.path.isfile(p):
            files.append(os.path.normpath(p))
    last_consultar_rtu_result = ConsultarResult(status=status, message=message, files=files, extra={})
    yield _result_line({"status": status, "message": message, "files": files})
