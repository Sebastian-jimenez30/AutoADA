from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional
from urllib.parse import quote
from datetime import datetime

from openpyxl import load_workbook

from services.vault_service import VaultService
from services.server_resolver import ServerResolver
from utils.cli import build_cmd

SUMMARY_VARIANTS = {"info", "success", "warning", "error"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUX_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
AUTOADA_DIR = os.path.join(AUX_ROOT, "AutoADA")
OUT_ROOT = os.path.join(AUTOADA_DIR, "out")
PRUEBAS_OUT = os.path.join(OUT_ROOT, "pruebas")
PRUEBAS_UPLOAD = os.path.join(OUT_ROOT, "pruebas_inputs")

if AUTOADA_DIR not in sys.path:
    sys.path.insert(0, AUTOADA_DIR)

SERVER_RESOLVER = ServerResolver(os.path.join(AUTOADA_DIR, "config"))
SERVER_RESOLVER._path = os.path.join(AUTOADA_DIR, "config", "servers.json")


@dataclass
class PruebasResult:
    status: str
    message: str
    files: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


last_pruebas_itcosas_v1_result: Optional[PruebasResult] = None


def _summary_line(message: str, variant: str = "info") -> str | None:
    clean = (message or "").strip()
    if not clean:
        return None
    normalized = variant.lower()
    if normalized not in SUMMARY_VARIANTS:
        normalized = "info"
    return f"SUMMARY::{clean}|{normalized}\n"


def _result_line(payload: dict[str, Any]) -> str:
    return f"RESULT::{json.dumps(payload, ensure_ascii=False)}\n"


def _run_subprocess_stream(
    cmd: list[str],
    label: str,
    env: dict[str, str],
    cwd: str,
) -> Generator[str, None, int]:
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


def _detect_empresas_pruebas() -> list[str]:
    try:
        host = socket.gethostname().lower()
        if host.startswith(("itco1", "tra1", "isa1cct5_p", "desktop-n14qm43", "isa1ccwx_p")):
            return ["ITCO", "TRA"]
        if host.startswith(("rep1", "rep2")):
            return ["REPS", "REPP"]
    except Exception:
        pass
    return ["ITCO", "TRA"]


def get_empresas() -> list[str]:
    return _detect_empresas_pruebas()


def get_dominios() -> list[str]:
    # Dominio fijo para pruebas v1: CC
    return ["CC"]


def _validate_datetime(fecha: str, hora: str) -> bool:
    try:
        datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S.%f")
        return True
    except Exception:
        return False


def itcosas_v1_pipeline(
    empresa: str,
    dominio: str,
    fecha: str,
    hora_inicio: str,
    hora_fin: str,
    checklist: str,
    eventos: str,
    varexp: str,
    tmw: str,
) -> Generator[str, None, None]:
    """Pipeline web para ITCOSAS v1 (pruebas)."""
    global last_pruebas_itcosas_v1_result
    last_pruebas_itcosas_v1_result = None
    extra_messages: list[str] = []

    def _store(status: str, message: str, files: list[str] | None = None, extra: dict[str, Any] | None = None):
        global last_pruebas_itcosas_v1_result
        last_pruebas_itcosas_v1_result = PruebasResult(
            status=status,
            message=message,
            files=files or [],
            extra=extra or {},
        )

    empresa = (empresa or "").strip().upper()
    dominio = "CC"

    if not empresa or not dominio:
        payload = {"status": "ERROR", "message": "Debes seleccionar empresa y dominio."}
        _store(payload["status"], payload["message"])
        yield _result_line(payload)
        return

    if not (_validate_datetime(fecha, hora_inicio) and _validate_datetime(fecha, hora_fin)):
        payload = {"status": "ERROR", "message": "Fecha u hora en formato inválido."}
        _store(payload["status"], payload["message"])
        yield _result_line(payload)
        return

    try:
        t0 = datetime.strptime(f"{fecha} {hora_inicio}", "%Y-%m-%d %H:%M:%S.%f")
        t1 = datetime.strptime(f"{fecha} {hora_fin}", "%Y-%m-%d %H:%M:%S.%f")
        if t0 > t1:
            payload = {"status": "ERROR", "message": "Hora inicio no puede ser mayor que hora fin."}
            _store(payload["status"], payload["message"])
            yield _result_line(payload)
            return
    except Exception:
        payload = {"status": "ERROR", "message": "Fecha u hora con formato inválido."}
        _store(payload["status"], payload["message"])
        yield _result_line(payload)
        return

    required_files = {
        "Checklist": checklist,
        "EventosDiario": eventos,
        "Varexp": varexp,
        "TMWgateway": tmw,
    }
    for label, path in required_files.items():
        if not path or not os.path.isfile(path):
            payload = {"status": "ERROR", "message": f"Falta archivo obligatorio: {label}"}
            _store(payload["status"], payload["message"])
            yield _result_line(payload)
            return

    try:
        env = VaultService.build_env()
    except Exception as exc:
        message = f"No se pudo construir el entorno: {exc}"
        _store("ERROR", message)
        yield _result_line({"status": "ERROR", "message": message})
        return

    servidor = SERVER_RESOLVER.generar_server(empresa, dominio)
    if not servidor:
        message = "No se pudo resolver el servidor para la empresa/dominio seleccionados."
        _store("ERROR", message)
        yield _result_line({"status": "ERROR", "message": message})
        return

    # HIS hosts: fallback si el vault no los trae
    his_fallback = {
        "ITCO": ["itco1his01", "itco1his02"],
        "TRA": ["itco1his01", "itco1his02"],
        "REPS": ["rep1his01", "rep1his02"],
        "REPP": ["rep1his01", "rep1his02"],
    }
    if "HIS_HOSTS" not in env:
        hosts = his_fallback.get(empresa)
        if hosts:
            env["HIS_HOSTS"] = ",".join(hosts)
            env["HIS_PRIMARY"] = hosts[0]
            if len(hosts) > 1:
                env["HIS_SECONDARY"] = hosts[1]

    outdir = os.path.join(OUT_ROOT, "pruebas")
    os.makedirs(outdir, exist_ok=True)
    artifacts = {
        "direcciones": os.path.join(outdir, "Direcciones.csv"),
        "soe_local": os.path.join(outdir, "SOE_Local.csv"),
        "his_data": os.path.join(outdir, "data.csv"),
        "soe_monarch": os.path.join(outdir, "SOE_Monarch.csv"),
        "soe_final": os.path.join(outdir, "SOE_completo.xlsx"),
    }

    def _stream_step(label: str, cmd: list[str]) -> int:
        stream = _run_subprocess_stream(cmd, label, env=env, cwd=AUTOADA_DIR)
        rc: int | None = None
        try:
            while True:
                chunk = next(stream)
                yield chunk
        except StopIteration as stop:
            rc = stop.value if isinstance(stop.value, int) else 0
        return rc if rc is not None else 0

    yield "Limpiando artefactos previos...\n"
    for f in artifacts.values():
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass

    # Importar SCADA (perfil pruebas_pyp)
    cmd_import = build_cmd("scripts.importar_all", servidor, empresa, "sca", "--usecase", "pruebas_pyp")
    rc_import = yield from _stream_step("IMPORT-SCADA", cmd_import)
    if rc_import != 0:
        msg = f"Importación SCADA falló (rc={rc_import})."
        extra_messages.append(msg)
        line = _summary_line(msg, "error")
        if line:
            yield line
        payload = {"status": "ERROR", "message": msg}
        _store(payload["status"], payload["message"], extra={"details": extra_messages})
        yield _result_line(payload)
        return
    line = _summary_line("Importación SCADA completada", "success")
    if line:
        extra_messages.append("Importación SCADA completada")
        yield line

    # Paso IOA
    cmd_ioa = build_cmd("scripts.itcosas_v1_ioa", f"--tmwgateway={tmw}", f"--varexp={varexp}", f"--outdir={outdir}")
    rc_ioa = yield from _stream_step("IOA", cmd_ioa)
    if rc_ioa != 0:
        msg = "Paso IOA falló."
        extra_messages.append(msg)
        line = _summary_line(msg, "error")
        if line:
            yield line
        payload = {"status": "ERROR", "message": msg}
        _store(payload["status"], payload["message"], extra={"details": extra_messages})
        yield _result_line(payload)
        return
    line = _summary_line("Direcciones.csv generado (IOA)", "success")
    if line:
        extra_messages.append("Direcciones.csv generado (IOA)")
        yield line

    # Paso SOE Local
    cmd_soe_local = build_cmd(
        "scripts.itcosas_v1_soe_local",
        f"--eventos={eventos}",
        f"--direcciones={artifacts['direcciones']}",
        f"--outdir={outdir}",
    )
    rc_soe_local = yield from _stream_step("SOE-LOCAL", cmd_soe_local)
    if rc_soe_local != 0:
        msg = "Paso SOE Local falló."
        extra_messages.append(msg)
        line = _summary_line(msg, "error")
        if line:
            yield line
        payload = {"status": "ERROR", "message": msg}
        _store(payload["status"], payload["message"], extra={"details": extra_messages})
        yield _result_line(payload)
        return
    line = _summary_line("SOE_Local.csv generado", "success")
    if line:
        extra_messages.append("SOE_Local.csv generado")
        yield line

    # Paso HIS (usa estaciones del checklist interno)
    his_host = env.get("HIS_PRIMARY") or env.get("HIS_HOSTS", "").split(",")[0] if env.get("HIS_HOSTS") else None
    his_args = [
        "scripts.import_his_soe",
        empresa,
        "--station",
        "%",
        "--fecha",
        fecha,
        "--hora_inicio",
        hora_inicio,
        "--hora_fin",
        hora_fin,
        "--outdir",
        outdir,
    ]
    if his_host:
        his_args.extend(["--host", his_host])
    cmd_his = build_cmd(*his_args)
    rc_his = yield from _stream_step("HIS", cmd_his)
    if rc_his != 0:
        msg = "Paso HIS falló."
        extra_messages.append(msg)
        line = _summary_line(msg, "error")
        if line:
            yield line
        payload = {"status": "ERROR", "message": msg}
        _store(payload["status"], payload["message"], extra={"details": extra_messages})
        yield _result_line(payload)
        return
    line = _summary_line("data.csv generado (HIS)", "success")
    if line:
        extra_messages.append("data.csv generado (HIS)")
        yield line

    # Paso SOE Monarch
    cmd_monarch = build_cmd("scripts.pyp_soe_monarch", empresa, checklist, artifacts["his_data"])
    rc_monarch = yield from _stream_step("SOE-MONARCH", cmd_monarch)
    if rc_monarch != 0:
        msg = "SOE Monarch falló."
        extra_messages.append(msg)
        line = _summary_line(msg, "error")
        if line:
            yield line
        payload = {"status": "ERROR", "message": msg}
        _store(payload["status"], payload["message"], extra={"details": extra_messages})
        yield _result_line(payload)
        return
    line = _summary_line("SOE_Monarch.csv generado", "success")
    if line:
        extra_messages.append("SOE_Monarch.csv generado")
        yield line

    # Paso Checklist final
    cmd_checklist = build_cmd("scripts.pyp_checklist", f"--checklist={checklist}", f"--outdir={outdir}")
    rc_checklist = yield from _stream_step("CHECKLIST", cmd_checklist)
    if rc_checklist != 0:
        msg = "Checklist final falló."
        extra_messages.append(msg)
        line = _summary_line(msg, "error")
        if line:
            yield line
        payload = {"status": "ERROR", "message": msg}
        _store(payload["status"], payload["message"], extra={"details": extra_messages})
        yield _result_line(payload)
        return
    line = _summary_line("SOE_completo.xlsx generado", "success")
    if line:
        extra_messages.append("SOE_completo.xlsx generado")
        yield line

    # Recopilar archivos generados
    files: list[str] = []
    if os.path.isdir(outdir):
        for fname in os.listdir(outdir):
            fpath = os.path.join(outdir, fname)
            if os.path.isfile(fpath):
                files.append(os.path.normpath(fpath))

    status = "SUCCESS"
    message = "ITCOSAS v1 completado."
    extra_payload: dict[str, Any] = {"details": extra_messages}
    if artifacts["soe_final"] in files:
        extra_payload["report_path"] = artifacts["soe_final"]
    _store(status, message, files=files, extra=extra_payload)
    payload = {"status": status, "message": message, "files": files, "details": extra_messages}
    yield _result_line(payload)


def get_last_pruebas_itcosas_v1_result() -> PruebasResult | None:
    return last_pruebas_itcosas_v1_result


def load_pruebas_itcosas_v1_preview(sheet: str | None = None, limit: int = 500) -> dict[str, Any] | None:
    result = last_pruebas_itcosas_v1_result
    if result is None:
        return None

    report_path = None
    if isinstance(result.extra, dict):
        report_path = result.extra.get("report_path")
    if report_path and not os.path.isabs(report_path):
        report_path = os.path.normpath(os.path.join(AUTOADA_DIR, report_path))
    if report_path and not os.path.isfile(report_path):
        report_path = None

    base_payload: dict[str, Any] = {
        "status": result.status,
        "message": result.message,
        "files": result.files,
        "details": result.extra.get("details", []) if isinstance(result.extra, dict) else [],
        "sheets": [],
        "active_sheet": None,
        "columns": [],
        "rows": [],
        "total": 0,
        "has_more": False,
        "limit": limit,
        "download_url": None,
    }

    if not report_path or not os.path.isfile(report_path):
        return base_payload

    wb = load_workbook(report_path, read_only=True, data_only=True)
    try:
        sheet_names = list(wb.sheetnames)
        if not sheet_names:
            return base_payload

        active_sheet = sheet if sheet in sheet_names else sheet_names[0]
        ws = wb[active_sheet]
        rows_iter = ws.iter_rows(values_only=True)

        try:
            headers_raw = next(rows_iter)
        except StopIteration:
            base_payload["sheets"] = sheet_names
            base_payload["active_sheet"] = active_sheet
            return base_payload

        headers: list[str] = []
        for idx, header in enumerate(headers_raw or (), start=1):
            if isinstance(header, str):
                clean = header.strip()
                headers.append(clean if clean else f"Columna {idx}")
            elif header is None:
                headers.append(f"Columna {idx}")
            else:
                headers.append(str(header))

        preview_rows: list[dict[str, Any]] = []
        row_count = 0
        has_more = False

        for row in rows_iter:
            row_count += 1
            row_dict: dict[str, Any] = {}
            for col_idx, header in enumerate(headers):
                value = row[col_idx] if col_idx < len(row) else None
                row_dict[header] = value
            if row_count <= limit:
                preview_rows.append(row_dict)
            else:
                has_more = True
                break

        download_url = f"/pruebas/itcosas-v1/result/download?path={quote(report_path)}"

        base_payload.update(
            {
                "sheets": sheet_names,
                "active_sheet": active_sheet,
                "columns": headers,
                "rows": preview_rows,
                "total": row_count,
                "has_more": has_more,
                "download_url": download_url,
                "report_path": report_path,
            }
        )
        return base_payload
    finally:
        wb.close()
