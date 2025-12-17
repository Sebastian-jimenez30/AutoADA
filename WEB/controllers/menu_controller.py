from __future__ import annotations

import os
import socket
from typing import Any, Generator

from utils.cli import build_cmd
from utils.last_update import last_update_text
from services.vault_service import VaultService
from services.server_resolver import ServerResolver

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUX_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
AUTOADA_DIR = os.path.join(AUX_ROOT, "AutoADA")
OUT_ROOT = os.path.join(AUTOADA_DIR, "out")
SERVER_RESOLVER = ServerResolver(os.path.join(AUTOADA_DIR, "config"))
SERVER_RESOLVER._path = os.path.join(AUTOADA_DIR, "config", "servers.json")

DEFAULT_DOMINIO = "CC"


def get_empresas() -> list[str]:
    try:
        host = socket.gethostname().lower()
        if host.startswith(("itco1", "tra1", "isa1cct5_p", "desktop-n14qm43", "isa1ccwx_p")):
            return ["ITCO", "TRA"]
        if host.startswith(("rep1", "rep2")):
            return ["REPS", "REPP"]
    except Exception:
        pass
    return ["ITCO", "TRA"]


def _summary_line(message: str, variant: str = "info") -> str | None:
    clean = (message or "").strip()
    if not clean:
        return None
    variant = variant.lower()
    if variant not in {"info", "success", "warning", "error"}:
        variant = "info"
    return f"SUMMARY::{clean}|{variant}\n"


def _result_line(status: str, message: str) -> str:
    import json

    payload = {"status": status, "message": message}
    return f"RESULT::{json.dumps(payload, ensure_ascii=False)}\n"


def get_status() -> dict[str, Any]:
    dominio = DEFAULT_DOMINIO
    empresa_list = get_empresas()
    data = []
    for emp in empresa_list:
        scada_folder = f"{dominio}SCADA"
        scada_text = last_update_text(AUTOADA_DIR, emp, [scada_folder])
        hsh_text = last_update_text(AUTOADA_DIR, emp, ["HSH"])
        ods_text = last_update_text(AUTOADA_DIR, emp, ["ODSTXT"])
        data.append(
            {
                "empresa": emp,
                "dominio": dominio,
                "scada": scada_text,
                "hsh": hsh_text,
                "ods": ods_text,
            }
        )
    return {"empresas": data}


def actualizar_datos_pipeline() -> Generator[str, None, None]:
    empresas = get_empresas()
    dominio = DEFAULT_DOMINIO

    try:
        env = VaultService.build_env()
    except Exception as exc:
        yield _result_line(
            "ERROR",
            f"No fue posible construir el entorno desde el vault ({exc}). Inicia sesión nuevamente.",
        )
        return

    def _summary(msg: str, variant: str = "info"):
        line = _summary_line(msg, variant)
        if line:
            yield line

    if not empresas:
        yield _result_line("ERROR", "No hay empresas configuradas para actualizar.")
        return

    yield from _summary("Actualizacion global iniciada")

    for empresa in empresas:
        servidor = SERVER_RESOLVER.generar_server(empresa, dominio)
        if not servidor:
            yield _result_line("ERROR", f"{empresa}: no se pudo resolver servidor (dominio {dominio}).")
            continue

        yield from _summary(f"{empresa}: importando SCADA/HSH/ODS")
        cmd_import = build_cmd("scripts.importar_all", servidor, empresa, "sca,hsh,ods", "--dominio", dominio)
        rc_import = yield from _run_subprocess(cmd_import, f"IMPORT-{empresa}", env=env)
        if rc_import != 0:
            yield _result_line("ERROR", f"{empresa}: importar_all termino con rc={rc_import}")
            continue

        # Convertir componentes
        for comp in ("sca", "hsh", "ods", "ods_csv"):
            tag = f"CONVERT-{empresa}-{comp.upper()}"
            args = ["scripts.Convertir_all", empresa, "Buscar_keys", "--only", comp]
            if comp == "sca":
                args.extend(["--dominio", dominio])
            cmd_conv = build_cmd(*args)
            yield from _summary(f"{empresa}: convirtiendo {comp.upper()}")
            rc_conv = yield from _run_subprocess(cmd_conv, tag, env=env)
            if rc_conv != 0:
                yield _result_line("ERROR", f"{empresa}: convertir {comp} termino con rc={rc_conv}")
                break
        else:
            yield from _summary(f"{empresa}: actualizacion completada", "success")

    yield _result_line("SUCCESS", "Actualizacion global finalizada")


def _run_subprocess(
    cmd: list[str],
    label: str,
    *,
    env: dict[str, str] | None = None,
) -> Generator[str, None, int]:
    import subprocess

    yield f"\n--- {label} ---\n"
    yield f"$ {' '.join(cmd)}\n"
    proc_env = (env or os.environ).copy()
    proc_env.setdefault("PYTHONUNBUFFERED", "1")
    proc_env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=AUTOADA_DIR,
        env=proc_env,
    )
    rc: int | None = None
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
    yield f"[{label}] Codigo de salida: {rc}\n"
    return rc
