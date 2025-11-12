from __future__ import annotations

import base64
import csv
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote

from openpyxl import load_workbook
import paramiko

from services.vault_service import VaultService
from services.server_resolver import ServerResolver
from utils.cli import build_cmd
from utils.data_checks import find_mode_data_ready

SUMMARY_VARIANTS = {"info", "success", "warning", "error"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUX_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
AUTOADA_DIR = os.path.join(AUX_ROOT, "AutoADA")
OUT_ROOT = os.path.join(AUTOADA_DIR, "out")
HSH_OUTPUT_DIR = os.path.join(OUT_ROOT, "HSH")
CREAR_TAG_DIR = os.path.join(OUT_ROOT, "crear_tag")
CREAR_TAG_REPORT = os.path.join(CREAR_TAG_DIR, "reporte_crear_tag.xlsx")
SCRIPTS_DIR = os.path.join(AUTOADA_DIR, "scripts")

if AUTOADA_DIR not in sys.path:
    sys.path.insert(0, AUTOADA_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from scripts import _Logger as Logger  # type: ignore
from scripts.functions import scada_online, sshserver  # type: ignore
from scripts.import_base import company_prefixes  # type: ignore

SCADA_HOSTS_FULL: Dict[str, list[str]] = {
    "ITCO": ["itco1sca01", "itco1sca02", "itco1qds01"],
    "TRA": ["tra1sca01", "tra1sca02"],
    "REPS": ["rep1sca01", "rep1sca02", "rep1qds01"],
    "REPP": ["rep2sca01", "rep2sca02", "rep2qds01"],
}

PI_SERVER_MAP: Dict[str, str] = {
    "ITCO": "PI-CO-ITCOTRA01",
    "TRA": "PI-CO-ITCOTRA01",
    "REPS": "PI-CO-ITCOTRA01",
    "REPP": "PI-CO-ITCOTRA01",
}

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


@dataclass
class PiSnapshotResult:
    lines: List[str]
    missing_lines: List[str]
    messages: List[str]
    snapshot_map: Dict[str, List[Dict[str, str]]]
    missing_map: Dict[str, List[str]]
    collected_at: Optional[str]
    has_failures: bool


def collect_pi_snapshots(
    *,
    app,
    tags_by_empresa: Dict[str, Set[str]],
    server_map: Dict[str, Optional[str]],
    console_write: Optional[Callable[[str, str], None]] = None,
    record_status: Optional[Callable[[str, str, Optional[bool], Optional[str]], None]] = None,
    empresa_principal: Optional[str] = None,
    derive_prefixes: Optional[Callable[[str], Iterable[str]]] = None,
    pi_server_map: Optional[Dict[str, str]] = None,
    log_filename: str = "pi_query.log",
) -> PiSnapshotResult:
    console_write = console_write or (lambda msg, tag="info": None)
    empresa_principal_u = empresa_principal.upper() if empresa_principal else None
    pi_server_map = pi_server_map or PI_SERVER_MAP

    lines: List[str] = []
    missing_lines: List[str] = []
    messages: List[str] = []
    snapshot_map: Dict[str, List[Dict[str, str]]] = {}
    missing_map: Dict[str, List[str]] = {}
    collected_at: Optional[str] = None
    has_failures = False

    env_pi = app.secure_env() if app else {}
    prev_env = {k: os.environ.get(k) for k in env_pi}
    os.environ.update(env_pi)

    try:
        pi_user = os.environ.get("USER_PI")
        pi_pass = os.environ.get("PASS_PI")
        if not pi_user or not pi_pass:
            msg = "PI: credenciales USER_PI/PASS_PI no disponibles en el entorno."
            lines.append(msg)
            messages.append(msg)
            for emp_candidate in (tags_by_empresa.keys() or server_map.keys()):
                emp_u = str(emp_candidate).upper()
                if record_status:
                    record_status(emp_u, "pi", False, msg)
            return PiSnapshotResult(lines, missing_lines, messages, snapshot_map, missing_map, collected_at, True)

        pi_user_ps = pi_user.replace('"', '`"')
        pi_pass_ps = pi_pass.replace('"', '`"')
        collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_dir = Path(getattr(app, "base_dir", os.getcwd())) / "out" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger, logger_console = Logger.initlog(str(log_dir / log_filename))
        except Exception:
            logger = logger_console = None  # type: ignore

        def _restore_env(prev: Dict[str, Optional[str]]) -> None:
            for key, value in prev.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        def _derive_prefixes_from_hint(hint: Optional[str]) -> List[str]:
            prefixes: List[str] = []
            if hint:
                lowered = hint.lower()
                cut = None
                for marker in ("sca", "qds", "his"):
                    idx = lowered.find(marker)
                    if idx != -1:
                        cut = idx
                        break
                prefix = hint[:cut] if cut is not None else hint
                if prefix:
                    prefixes.append(prefix)
            return prefixes

        def _collect_prefixes(emp_u: str, hint: Optional[str]) -> List[str]:
            prefixes: List[str] = []
            prefixes.extend(_derive_prefixes_from_hint(hint))
            env_sca_hosts = os.environ.get("SCA_HOSTS")
            if env_sca_hosts:
                for host in env_sca_hosts.split(","):
                    host = host.strip()
                    if host:
                        prefixes.extend(_derive_prefixes_from_hint(host))
            for pref in company_prefixes(emp_u) or []:
                if pref and pref not in prefixes:
                    prefixes.append(pref)
            return [pref for pref in prefixes if pref]

        def _encoded_ps_single(emp_u: str, tag: str, pi_server: str) -> str:
            tag_json = json.dumps(tag)
            template = """
$ErrorActionPreference = 'Stop'
Add-Type -Path "C:\\Program Files (x86)\\PIPC\\AF\\PublicAssemblies\\4.0\\OSIsoft.AFSDK.dll"
$piServers = [OSIsoft.AF.PI.PIServers]::GetPIServers()
$piServer = $piServers['{pi_server}']
$securePassword = ConvertTo-SecureString "{pi_pass_ps}" -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential("{pi_user_ps}", $securePassword)
$piServer.Connect($credential)
$target = ConvertFrom-Json @'
{tag_json}
'@
$result = @()
foreach ($piPoint in [OSIsoft.AF.PI.PIPoint]::FindPIPoints($piServer, "{emp_u}*SCADA*", $true)) {{
    if ($piPoint.Name -like "*${{target}}*") {{
        $cv = $piPoint.CurrentValue()
        $result += [PSCustomObject]@{{
            Name = $piPoint.Name
            Value = $cv.Value.ToString()
            Timestamp = $cv.Timestamp.ToString()
        }}
        break
    }}
}}
"__PI_JSON__:" + ($result | ConvertTo-Json -Depth 4 -Compress)
"""
            ps_script = template.format(
                pi_server=pi_server,
                pi_pass_ps=pi_pass_ps,
                pi_user_ps=pi_user_ps,
                tag_json=tag_json,
                emp_u=emp_u,
            )
            encoded = base64.b64encode(ps_script.encode("utf-16-le")).decode("utf-8")
            return f"powershell -NoLogo -NonInteractive -EncodedCommand {encoded}"

        def _record(emp: str, message: str, ok: Optional[bool]) -> None:
            if record_status:
                record_status(emp, "pi", ok, message)

        for emp_raw, tags in sorted(tags_by_empresa.items(), key=lambda item: item[0]):
            emp_u = str(emp_raw).upper()
            tag_list = sorted({t.strip() for t in tags if t})
            if not tag_list:
                _record(emp_u, "Sin tags generados para consultar", True)
                continue

            if empresa_principal_u and emp_u != empresa_principal_u:
                _record(emp_u, "Valores en PI: no aplica (solo empresa principal)", True)
                continue

            pi_server = pi_server_map.get(emp_u, pi_server_map.get("ITCO", "PI-CO-ITCOTRA01"))
            prefixes = list(derive_prefixes(emp_u)) if derive_prefixes else []
            if not prefixes:
                prefixes = _collect_prefixes(emp_u, server_map.get(emp_u))
            if not prefixes:
                msg = f"PI: no se encontraron prefijos SCADA/HIS para {emp_u}"
                lines.append(msg)
                messages.append(msg)
                has_failures = True
                _record(emp_u, msg, False)
                continue

            aggregated_rows: List[Dict[str, str]] = []
            missing_tags: List[str] = []

            for tag in tag_list:
                tag_rows: Optional[List[Dict[str, str]]] = None
                last_error: Optional[str] = None

                for prefix in prefixes:
                    if tag_rows:
                        break

                    for sca_suffix in ("sca01", "sca02"):
                        sca_host = f"{prefix}{sca_suffix}"
                        console_write(f"[PI] Conectando a SCADA {sca_host} para {tag} ...", "info")
                        client_sca = None
                        try:
                            client_sca = sshserver(sca_host, logger, logger_console)
                        except Exception as exc:
                            last_error = str(exc)
                            console_write(f"[PI] Error conectando a SCADA {sca_host}: {exc}", "error")
                            _record(emp_u, f"{tag}: error conectando a {sca_host}: {exc}", None)
                            continue

                        if client_sca is None:
                            last_error = "sshserver devolvió None"
                            console_write(f"[PI] {sca_host}: sshserver devolvió None", "error")
                            _record(emp_u, f"{tag}: {sca_host} sshserver devolvió None", None)
                            continue

                        transport = client_sca.get_transport()
                        if transport is None or not transport.is_active():
                            last_error = "transporte SSH inactivo"
                            console_write(f"[PI] {sca_host}: transporte SSH inactivo", "error")
                            _record(emp_u, f"{tag}: {sca_host} transporte SSH inactivo", None)
                            try:
                                client_sca.close()
                            except Exception:
                                pass
                            continue

                        try:
                            for his_suffix in ("his01", "his02"):
                                his_host = f"{prefix}{his_suffix}"
                                channel = None
                                client_his = None
                                try:
                                    console_write(f"[PI]   Tunel a {his_host} para {tag} ...", "info")
                                    channel = transport.open_channel(
                                        "direct-tcpip", (his_host, 22), ("127.0.0.1", 0)
                                    )
                                    client_his = paramiko.SSHClient()
                                    client_his.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                                    client_his.connect(
                                        hostname=his_host,
                                        username=pi_user,
                                        password=pi_pass,
                                        sock=channel,
                                        look_for_keys=False,
                                    )

                                    command = _encoded_ps_single(emp_u, tag, pi_server)
                                    if Logger is not None and logger is not None:
                                        Logger.write_log().log_all(
                                            "info", f"[PI] comando {command}", logger_console, logger
                                        )
                                    stdin, stdout, stderr = client_his.exec_command(command)
                                    output = stdout.read().decode("utf-8", "ignore")
                                    err_output = stderr.read().decode("utf-8", "ignore").strip()
                                    if err_output:
                                        console_write(f"[PI] {his_host} STDERR: {err_output}", "warn")

                                    marker = "__PI_JSON__:"
                                    idx = output.find(marker)
                                    if idx == -1:
                                        last_error = err_output or output.strip() or "respuesta inesperada"
                                        console_write(
                                            f"[PI] {his_host}: respuesta inesperada -> {last_error}", "warn"
                                        )
                                        _record(emp_u, f"{tag}: {his_host} respuesta inesperada", None)
                                        continue

                                    json_text = output[idx + len(marker) :].strip()
                                    raw_rows = json.loads(json_text) if json_text else []

                                    normalized: List[Dict[str, str]] = []
                                    if isinstance(raw_rows, list):
                                        for item in raw_rows:
                                            if isinstance(item, dict):
                                                normalized.append(
                                                    {
                                                        "Name": str(item.get("Name", item.get("name", "?"))),
                                                        "Value": str(item.get("Value", item.get("value", ""))),
                                                        "Timestamp": str(item.get("Timestamp", item.get("timestamp", ""))),
                                                    }
                                                )
                                    elif isinstance(raw_rows, dict):
                                        normalized.append(
                                            {
                                                "Name": str(raw_rows.get("Name", raw_rows.get("name", "?"))),
                                                "Value": str(raw_rows.get("Value", raw_rows.get("value", ""))),
                                                "Timestamp": str(raw_rows.get("Timestamp", raw_rows.get("timestamp", ""))),
                                            }
                                        )

                                    if normalized:
                                        tag_rows = normalized
                                        aggregated_rows.extend(normalized)
                                        _record(emp_u, f"{tag}: {len(normalized)} valores desde {his_host}", None)
                                        break

                                    last_error = "sin valores"
                                    console_write(f"[PI] {his_host}: sin valores para {tag}", "warn")
                                except Exception as exc:
                                    last_error = str(exc)
                                    console_write(f"[PI] Error {sca_host}->{his_host} ({tag}): {exc}", "error")
                                    _record(emp_u, f"{tag}: error {sca_host}->{his_host}: {exc}", None)
                                finally:
                                    if client_his is not None:
                                        client_his.close()
                                    if channel is not None:
                                        channel.close()
                                if tag_rows:
                                    break
                        finally:
                            try:
                                if client_sca is not None:
                                    client_sca.close()
                            except Exception:
                                pass

                        if tag_rows:
                            break

                if not tag_rows:
                    missing_tags.append(tag)
                    has_failures = True
                    warning = f"{emp_u}:{tag}:{last_error or 'sin datos'}"
                    missing_lines.append(warning)
                    console_write(
                        f"[PI] {emp_u}: no se obtuvo informacion para {tag} ({last_error or 'sin datos'})", "warn"
                    )
                    _record(emp_u, f"{tag}: {last_error or 'sin datos'}", False)
                else:
                    console_write(f"[PI] {emp_u}: valores capturados para {tag}", "info")

            snapshot_map[emp_u] = aggregated_rows
            missing_map[emp_u] = missing_tags

            if aggregated_rows:
                pretty = ", ".join(f"{row.get('Name', '?')} = {row.get('Value', '?')}" for row in aggregated_rows)
                msg = f"{emp_u}: {pretty}"
                lines.append(msg)
                messages.append(msg)
                if record_status and not missing_tags:
                    record_status(emp_u, "pi", True, msg)
            if missing_tags:
                miss_msg = f"{emp_u}: sin datos para {', '.join(missing_tags)}"
                lines.append(miss_msg)
                messages.append(miss_msg)

            if not aggregated_rows and not missing_tags:
                _record(emp_u, "Sin valores consultados", True)

        return PiSnapshotResult(lines, missing_lines, messages, snapshot_map, missing_map, collected_at, has_failures)
    finally:
        _restore_env(prev_env)


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
) -> Generator[str, None, None]:
    global last_crear_result

    empresa = (empresa or "").strip().upper()
    dominio = (dominio or "").strip().upper() or "CC"
    archivo_nombre = archivo_nombre or os.path.basename(archivo_path)

    def _store_result(status: str, message: str, files: list[str] | None = None, extra: dict[str, Any] | None = None):
        global last_crear_result
        last_crear_result = CrearResult(
            status=status,
            message=message,
            files=files or [],
            extra=extra or {},
        )

    extra_messages: list[str] = []


    def _summary_line_local(message: str, variant: str = "info") -> str | None:
        clean = (message or "").strip()
        if not clean:
            return None
        normalized = variant.lower()
        if normalized not in SUMMARY_VARIANTS:
            normalized = "info"
        extra_messages.append(clean)
        return f"SUMMARY::{clean}|{normalized}\n"

    def _yield_summary(message: str, variant: str = "info"):
        line = _summary_line_local(message, variant)
        if line:
            yield line

    yield f"Iniciando proceso Crear Tag HSH para empresa={empresa} dominio={dominio} archivo={archivo_nombre}\n"
    yield from _yield_summary(f"{empresa}: proceso iniciado")


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
    needs_update = True
    yield f"Datos locales disponibles para {empresa}: {ready} (se forzará actualización previa)\n"
    yield f"Detalle OUT/SCADA/HSH/ODSTXT: {details}\n"
    yield from _yield_summary(f"{empresa}: preparando datos locales")

    report_paths: set[str] = set()
    info_paths: set[str] = set()
    extra_paths: set[str] = set()
    report_excel_path: Optional[str] = None
    inserted_keys_full: dict[str, set[str]] = {}
    inserted_keys_map: dict[str, dict[str, set[str]]] = {}
    inserted_tags_full: dict[str, set[str]] = {}
    inserted_pairs_map: dict[str, list[tuple[str, str]]] = {}
    pending_apply_keys: dict[str, list[str]] = {}
    apply_import_servers: dict[str, str] = {}
    hsh_servers_used: dict[str, str] = {}
    last_sca_host_seen: Optional[str] = None
    verification_status: dict[str, dict[str, dict[str, Any]]] = {}
    verification_order: list[str] = []

    def _split_tag_name(name: str) -> tuple[str, str]:
        base = str(name or "").strip()
        suffix = ""
        if "." in base:
            base, suffix = base.rsplit(".", 1)
        return base, suffix

    def _derive_key_from_base(base: str) -> str:
        clean = base.strip()
        return clean.rsplit(":", 1)[0] if ":" in clean else clean

    def _ensure_status(emp: str) -> dict[str, dict[str, Any]]:
        emp_u = emp.upper()
        if emp_u not in verification_status:
            verification_status[emp_u] = {
                step: {"ok": None, "messages": []}
                for step in ("import", "convert", "lookup", "scada", "pi")
            }
            verification_order.append(emp_u)
        return verification_status[emp_u]

    def _record_status(emp: str, step: str, ok: Optional[bool] = None, message: Optional[str] = None) -> None:
        status = _ensure_status(emp).get(step)
        if status is None:
            return
        if ok is not None:
            current = status.get("ok")
            if current is None:
                status["ok"] = ok
            elif current and not ok:
                status["ok"] = False
            elif current is False and ok:
                status["ok"] = False
            else:
                status["ok"] = ok if current is None else current
        if message:
            messages = status.setdefault("messages", [])
            if message not in messages:
                messages.append(message)

    def _lookup_paths_for(emp: str) -> list[Path]:
        emp_u = emp.upper()
        return [
            Path(AUTOADA_DIR) / "out" / emp_u / "HSH" / "lookup_table.csv",
            Path(OUT_ROOT) / emp_u / "HSH" / "lookup_table.csv",
        ]

    def _check_local_keys(emp: str, keys: Iterable[str]) -> tuple[list[str], list[str]]:
        keys_set = {k.strip() for k in keys if k.strip()}
        if not keys_set:
            return [], []
        present: set[str] = set()
        for path in _lookup_paths_for(emp):
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        value = (row.get("key") or row.get("Key") or "").strip()
                        if value in keys_set:
                            present.add(value)
            except Exception:
                continue
        missing = sorted(keys_set - present)
        return sorted(present), missing

    def _build_verification_summary() -> list[str]:
        lines: list[str] = []
        for emp in verification_order:
            status = verification_status.get(emp, {})
            lines.append(f"{emp}:")
            for step, label in (
                ("import", "Importación HSH"),
                ("convert", "Conversión HSH"),
                ("lookup", "LookupTables"),
                ("scada", "SCADA"),
                ("pi", "PI"),
            ):
                data = status.get(step, {})
                ok = data.get("ok")
                messages = data.get("messages") or []
                estado = "OK" if ok else ("ERROR" if ok is False else "PENDIENTE")
                lines.append(f"  - {label}: {estado}" + (f" ({'; '.join(messages)})" if messages else ""))
            lines.append("")
        while lines and not lines[-1]:
            lines.pop()
        return lines

    def _apply_scada_updates_for_web() -> tuple[list[str], bool]:
        if not inserted_keys_map:
            return [], False

        if sshserver is None:
            msg = "SCADA: función sshserver no disponible."
            for emp in inserted_keys_map.keys():
                _record_status(emp, "scada", False, msg)
            return [msg], True

        env_secure = env
        prev_env = {k: os.environ.get(k) for k in env_secure}
        os.environ.update(env_secure)

        log_dir = Path(AUTOADA_DIR) / "out" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)

        if Logger is None:
            msg = "SCADA: Logger no disponible."
            for emp in inserted_keys_map.keys():
                _record_status(emp, "scada", False, msg)
            for key, value in prev_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            return [msg], True

        try:
            logger, logger_console = Logger.initlog(str(log_dir / "scada_crear_tag.log"))
        except Exception as exc:
            msg = f"SCADA: no se pudo inicializar logger ({exc})."
            for emp in inserted_keys_map.keys():
                _record_status(emp, "scada", False, msg)
            for key, value in prev_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            return [msg], True

        messages: list[str] = []
        has_fail = False
        analog_suffixes = {"VALUE", "ESTIMATED"}

        try:
            for emp_u, base_map in inserted_keys_map.items():
                if not base_map:
                    continue

                domain_hosts: Dict[str, Set[str]] = {"CC": set(), "QA": set()}
                for host in SCADA_HOSTS_FULL.get(emp_u, []) or []:
                    host = (host or "").strip()
                    if not host:
                        continue
                    domain = "QA" if "qds" in host.lower() else "CC"
                    domain_hosts.setdefault(domain, set()).add(host)

                for dom in ("CC", "QA"):
                    try:
                        host = SERVER_RESOLVER.generar_server(emp_u, dom)
                    except Exception:
                        host = None
                    if host:
                        domain_hosts.setdefault(dom, set()).add(host)

                host_entries = [
                    (dom, host)
                    for dom in ("CC", "QA")
                    for host in sorted(domain_hosts.get(dom, set()))
                ]
                if not host_entries:
                    msg = f"{emp_u}: no se encontraron servidores SCADA configurados."
                    messages.append(msg)
                    _record_status(emp_u, "scada", False, msg)
                    has_fail = True
                    continue

                for domain_label, host in host_entries:
                    label = f"{emp_u} ({host})"
                    client = None
                    try:
                        client = sshserver(host, logger, logger_console)
                        if client is None:
                            raise RuntimeError("sshserver devolvió None")
                        _record_status(emp_u, "scada", None, f"Conexión establecida con {host}")
                        host_online = None
                        try:
                            host_online = scada_online(client, logger, logger_console)
                        except Exception as exc:
                            messages.append(f"{label}: error verificando estado ONLINE ({exc})")
                        if host_online:
                            messages.append(f"{label}: estado ONLINE detectado ({host_online})")
                    except Exception as exc:
                        msg = f"{label}: no se pudo conectar - {exc}"
                        messages.append(msg)
                        _record_status(emp_u, "scada", False, msg)
                        has_fail = True
                        if client:
                            try:
                                client.close()
                            except Exception:
                                pass
                        continue

                    try:
                        for base_key, suffixes in base_map.items():
                            suffix_set = {s.upper() for s in suffixes if s}
                            bit_specs: set[tuple[int, int]] = set()
                            if suffix_set & analog_suffixes:
                                bit_specs.add((5, 1))
                                if "ESTIMATED" in suffix_set:
                                    bit_specs.add((5, 2))
                            else:
                                bit_specs.add((4, 1))
                            if not bit_specs:
                                bit_specs.add((4, 1))

                            for tipo, bit in sorted(bit_specs):
                                cmd = f". ~/.bash_profile && dbset -k 10 {tipo} 12 {base_key} {bit} = 1"
                                try:
                                    stdin, stdout, stderr = client.exec_command(cmd)
                                    rc_cmd = stdout.channel.recv_exit_status()
                                    if rc_cmd == 0:
                                        msg = f"{label}: OK {base_key} bit {bit}"
                                        messages.append(msg)
                                        _record_status(emp_u, "scada", True, msg)
                                    else:
                                        err = stderr.read().decode("utf-8", "ignore").strip()
                                        msg = f"{label}: fallo {base_key} bit {bit} (rc={rc_cmd}) {err}"
                                        messages.append(msg)
                                        _record_status(emp_u, "scada", False, msg)
                                        has_fail = True
                                except Exception as exc:
                                    msg = f"{label}: error {base_key} bit {bit}: {exc}"
                                    messages.append(msg)
                                    _record_status(emp_u, "scada", False, msg)
                                    has_fail = True
                    finally:
                        try:
                            if client:
                                client.close()
                        except Exception:
                            pass
        finally:
            for key, value in prev_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        return messages, has_fail

    def _derive_prefixes(emp_u: str) -> list[str]:
        prefixes: list[str] = []
        hint = apply_import_servers.get(emp_u)
        if hint:
            lowered = hint.lower()
            cut = next((lowered.find(marker) for marker in ("sca", "qds", "his") if marker in lowered), -1)
            pref = hint[:cut] if cut != -1 else hint
            if pref:
                prefixes.append(pref)
        for pref in company_prefixes(emp_u) or []:
            if pref and pref not in prefixes:
                prefixes.append(pref)
        return [p for p in prefixes if p]

    def _prepare_pi_sheet_rows(
        pi_result: PiSnapshotResult | None,
        expected_tags: dict[str, set[str]],
        pairs_lookup: dict[str, list[tuple[str, str]]],
    ) -> tuple[list[str], list[list[str]]] | None:
        snapshot_map = {str(emp).upper(): rows or [] for emp, rows in (pi_result.snapshot_map.items() if pi_result else [])}
        missing_map = {str(emp).upper(): values or [] for emp, values in (pi_result.missing_map.items() if pi_result else [])}
        normalized_expected: dict[str, set[str]] = {}
        for emp, tags in expected_tags.items():
            tag_set = {str(tag).strip() for tag in (tags or set()) if str(tag).strip()}
            if tag_set:
                normalized_expected[emp.upper()] = tag_set
        normalized_pairs: dict[str, dict[str, str]] = {}
        for emp, pairs in pairs_lookup.items():
            emp_u = emp.upper()
            mapping = normalized_pairs.setdefault(emp_u, {})
            for key_name, tag_name in pairs or []:
                base_tag, _ = _split_tag_name(tag_name)
                if base_tag:
                    mapping[base_tag] = key_name

        suffix_order: list[str] = []
        suffix_labels: dict[str, str] = {}
        suffix_positions: dict[str, int] = {}

        def _normalize_suffix(raw: str) -> tuple[str, str]:
            token = (raw or "").strip()
            if not token:
                return "VALUE", "Value"
            token_upper = token.upper()
            if token_upper == "VALUE":
                return "VALUE", "Value"
            if token_upper == "ESTIMATED":
                return "ESTIMATED", "Estimated"
            if token_upper in {"STATE", "STATUS"}:
                return token_upper, token_upper.capitalize()
            if token_upper in {"Q", "P"}:
                return token_upper, token_upper
            return token_upper, token

        def _register_suffix(raw: str) -> str:
            key, label = _normalize_suffix(raw)
            if key not in suffix_labels:
                suffix_labels[key] = label
                suffix_order.append(key)
                suffix_positions[key] = len(suffix_positions)
            return key

        pi_entries: dict[tuple[str, str], dict[str, Any]] = {}

        def _entry(emp_u: str, base_tag: str) -> dict[str, Any]:
            key = (emp_u, base_tag)
            if key not in pi_entries:
                mapped_key = normalized_pairs.get(emp_u, {}).get(base_tag)
                pi_entries[key] = {
                    "empresa": emp_u,
                    "base_tag": base_tag,
                    "key": mapped_key or _derive_key_from_base(base_tag),
                    "values": {},
                    "expected": set(),
                }
            else:
                entry = pi_entries[key]
                if not entry.get("key"):
                    mapped_key = normalized_pairs.get(emp_u, {}).get(base_tag)
                    if mapped_key:
                        entry["key"] = mapped_key
            return pi_entries[key]

        for emp, tags in sorted(normalized_expected.items()):
            for tag_name in sorted(tags):
                base_tag, suffix_raw = _split_tag_name(tag_name)
                suffix_key = _register_suffix(suffix_raw)
                entry = _entry(emp, base_tag)
                expected: set[str] = entry["expected"]
                expected.add(suffix_key)

        for emp, rows in sorted(snapshot_map.items()):
            for row in rows:
                name = str(row.get("Name") or "").strip()
                if not name:
                    continue
                base_tag, suffix_raw = _split_tag_name(name)
                suffix_key = _register_suffix(suffix_raw)
                entry = _entry(emp, base_tag)
                values: dict[str, str] = entry["values"]
                value_raw = row.get("Value")
                values[suffix_key] = "" if value_raw is None else str(value_raw)
                expected: set[str] = entry["expected"]
                expected.discard(suffix_key)

        for emp, missing in sorted(missing_map.items()):
            for tag_name in missing:
                base_tag, suffix_raw = _split_tag_name(tag_name)
                suffix_key = _register_suffix(suffix_raw)
                entry = _entry(emp, base_tag)
                values: dict[str, str] = entry["values"]
                if suffix_key not in values:
                    values[suffix_key] = "No Data"
                expected: set[str] = entry["expected"]
                expected.discard(suffix_key)

        if not pi_entries:
            return None

        suffix_priority = {"Q": 0, "P": 1, "VALUE": 2, "ESTIMATED": 3, "STATE": 4, "STATUS": 5}
        ordered_suffixes = sorted(
            suffix_order,
            key=lambda key: (suffix_priority.get(key, 100), suffix_positions.get(key, 0)),
        )
        if not ordered_suffixes:
            ordered_suffixes = ["VALUE"]
            suffix_labels.setdefault("VALUE", "Value")

        headers = ["Empresa", "Key", "Tag"] + [suffix_labels[key] for key in ordered_suffixes]
        rows_output: list[list[str]] = []
        for (emp, base_tag), entry in sorted(pi_entries.items(), key=lambda item: (item[0][0], item[0][1])):
            values = entry["values"]
            expected = entry["expected"]
            key_name = entry.get("key") or _derive_key_from_base(base_tag)
            row = [emp, key_name, base_tag]
            for suffix_key in ordered_suffixes:
                if suffix_key in values:
                    row.append(values[suffix_key])
                elif suffix_key in expected:
                    row.append("No Data")
                else:
                    row.append("")
            rows_output.append(row)

        return headers, rows_output

    def _update_pi_sheet(
        report_path: str,
        pi_result: PiSnapshotResult,
        expected_tags: dict[str, set[str]],
        pairs_lookup: dict[str, list[tuple[str, str]]],
    ) -> None:
        payload = _prepare_pi_sheet_rows(pi_result, expected_tags, pairs_lookup)
        if not payload:
            return
        headers, rows = payload
        target_path = os.path.normpath(report_path)
        if not os.path.isabs(target_path):
            target_path = os.path.normpath(os.path.join(AUTOADA_DIR, target_path))
        if not os.path.isfile(target_path):
            return
        if load_workbook is None:
            raise RuntimeError("openpyxl no está disponible para actualizar el reporte.")
        workbook = load_workbook(target_path)
        try:
            if "PI" in workbook.sheetnames:
                ws_existing = workbook["PI"]
                workbook.remove(ws_existing)
            ws_pi = workbook.create_sheet("PI")
            ws_pi.append(headers)
            for row in rows:
                ws_pi.append(row)
            workbook.save(target_path)
        finally:
            workbook.close()

    def _collect_pi_verification(tags_for_pi: Iterable[str]) -> tuple[list[str], bool, PiSnapshotResult | None]:
        tags_set = {tag.strip() for tag in tags_for_pi if tag and tag.strip()}
        if not tags_set:
            return [], False, None

        dummy_app = _DummyApp(env, AUTOADA_DIR)
        lines: list[str] = []

        def _console_write(msg: str, tag: str = "info") -> None:
            lines.append(f"[PI][{tag.upper()}] {msg}")

        def _status_hook(emp: str, step: str, ok: Optional[bool], message: Optional[str]) -> None:
            _record_status(emp, "pi", ok, message)

        emp_upper = empresa.upper()
        server_map = {
            emp_upper: apply_import_servers.get(emp_upper) or SERVER_RESOLVER.generar_server(emp_upper, "CC")
        }

        result_pi = collect_pi_snapshots(
            app=dummy_app,
            tags_by_empresa={emp_upper: tags_set},
            server_map=server_map,
            console_write=_console_write,
            record_status=_status_hook,
            empresa_principal=empresa,
            derive_prefixes=_derive_prefixes,
            pi_server_map=PI_SERVER_MAP,
        )

        if result_pi.messages:
            for msg in result_pi.messages:
                lines.append(f"[PI][INFO] {msg}")
        if result_pi.missing_lines:
            for msg in result_pi.missing_lines:
                lines.append(f"[PI][WARN] {msg}")
        for json_line in result_pi.lines:
            lines.append(f"[PI][RAW] {json_line}")
        snapshot_rows = result_pi.snapshot_map.get(emp_upper, []) if result_pi.snapshot_map else []
        for row in snapshot_rows:
            name = row.get("Name", "?")
            value = row.get("Value", "?")
            timestamp = row.get("Timestamp", "?")
            lines.append(f"[PI][DATA] {name} = {value} @ {timestamp}")
        if result_pi.missing_map:
            missing = result_pi.missing_map.get(emp_upper, [])
            if missing:
                lines.append(f"[PI][MISSING] {', '.join(missing)}")
        return lines, result_pi.has_failures, result_pi

    def _handle_marker(line: str):
        nonlocal report_excel_path, last_sca_host_seen
        line = line.strip()
        if not line:
            return
        if line.startswith("REPORT_PATH:"):
            path = line.split(":", 1)[1].strip()
            report_paths.add(path)
            if path.lower().endswith("reporte_crear_tag.xlsx"):
                report_excel_path = path
        elif line.startswith("INFO_PATH:"):
            path = line.split(":", 1)[1].strip()
            info_paths.add(path)
            extra_paths.add(path)
        elif line.startswith("QUERY_PATH:"):
            path = line.split(":", 1)[1].strip()
            info_paths.add(path)
            extra_paths.add(path)
        elif line.startswith("SUMMARY:"):
            msg = line.split(":", 1)[1].strip()
            if msg:
                extra_messages.append(msg)
        elif line.startswith("Intentando conexion:"):
            try:
                seg = line.split("SCA=", 1)[1]
                sca_host = seg.split("->", 1)[0].strip()
                if sca_host:
                    last_sca_host_seen = sca_host
            except Exception:
                pass
        elif line.startswith("APPLY_SERVER:"):
            try:
                _, payload = line.split("APPLY_SERVER:", 1)
                emp_part, server_part = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                server_used = server_part.strip()
                if emp_key and server_used:
                    hsh_servers_used[emp_key] = server_used
            except ValueError:
                pass
        elif line.startswith("APPLY_SSH:"):
            try:
                _, payload = line.split("APPLY_SSH:", 1)
                emp_part, server_part = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                ssh_host = server_part.strip()
                if emp_key and ssh_host:
                    apply_import_servers[emp_key] = ssh_host
            except ValueError:
                pass
        elif line.startswith("APPLY_KEYS:"):
            try:
                _, payload = line.split("APPLY_KEYS:", 1)
                emp_part, keys_part = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                keys = [k.strip() for k in keys_part.split(",") if k.strip()]
                if keys:
                    inserted_keys_full.setdefault(emp_key, set()).update(keys)
                    base_map = inserted_keys_map.setdefault(emp_key, {})
                    for full_key in keys:
                        base, dot, suffix = full_key.partition(".")
                        base_map.setdefault(base, set()).add(suffix if dot else "")
                    pending_apply_keys.setdefault(emp_key, []).extend(keys)
            except ValueError:
                pass
        elif line.startswith("APPLY_TAGS:"):
            try:
                _, payload = line.split("APPLY_TAGS:", 1)
                emp_part, tags_part = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                tags = [t.strip() for t in tags_part.split(",") if t.strip()]
                if tags:
                    inserted_tags_full.setdefault(emp_key, set()).update(tags)
                    pending_keys = pending_apply_keys.get(emp_key, [])
                    leftover_tags = tags
                    if pending_keys:
                        pair_count = min(len(pending_keys), len(tags))
                        if pair_count:
                            pairs = list(zip(pending_keys[:pair_count], tags[:pair_count]))
                            inserted_pairs_map.setdefault(emp_key, []).extend(pairs)
                        pending_keys = pending_keys[pair_count:]
                        if pending_keys:
                            pending_apply_keys[emp_key] = pending_keys
                        else:
                            pending_apply_keys.pop(emp_key, None)
                        leftover_tags = tags[pair_count:]
                    if leftover_tags:
                        derived_pairs: list[tuple[str, str]] = []
                        for tag_name in leftover_tags:
                            base_tag, _ = _split_tag_name(tag_name)
                            derived_key = _derive_key_from_base(base_tag)
                            if derived_key:
                                derived_pairs.append((derived_key, tag_name))
                        if derived_pairs:
                            inserted_pairs_map.setdefault(emp_key, []).extend(derived_pairs)
            except ValueError:
                pass
        elif line.startswith("APPLY_OK:"):
            try:
                _, payload = line.split("APPLY_OK:", 1)
                emp_part, _ = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                if emp_key and last_sca_host_seen:
                    apply_import_servers.setdefault(emp_key, last_sca_host_seen)
            except Exception:
                pass

    def _stream_script(label: str, cmd: list[str]) -> int:
        stream = _run_subprocess_stream(cmd, label, env=env, cwd=AUTOADA_DIR)
        rc: int | None = None
        try:
            while True:
                chunk = next(stream)
                # Extraer la parte real del mensaje para interpretar marcadores
                raw = chunk
                if "[" in raw and "]" in raw:
                    raw = raw.split("]", 1)[1]
                _handle_marker(raw.strip())
                yield chunk
        except StopIteration as stop:
            rc = stop.value if isinstance(stop.value, int) else 0
        return rc if rc is not None else 0

    if needs_update:
        if respaldo and not servidor_respaldo:
            message = f"No se pudo resolver el servidor respaldo para {respaldo}."
            _store_result("ERROR", message)
            yield _result_line({"status": "ERROR", "message": message})
            return
        yield from _yield_summary("Actualizando datos locales (importar/convertir)")

        pre_commands: list[tuple[str, list[str]] | None] = [
            ("IMPORT-PRINCIPAL", build_cmd("scripts.importar_all", servidor_principal, empresa, "sca,hsh", "--usecase", "hsh_crear_tag")),
            ("IMPORT-RESPALDO", build_cmd("scripts.importar_all", servidor_respaldo, respaldo, "sca,hsh", "--usecase", "hsh_crear_tag")) if respaldo and servidor_respaldo else None,
            ("CONVERT-SCA-PRINCIPAL", build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "sca")),
            ("CONVERT-HSH-PRINCIPAL", build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "hsh")),
            ("CONVERT-SCA-RESPALDO", build_cmd("scripts.Convertir_all", respaldo, "Validar_HSH", "--only", "sca")) if respaldo else None,
            ("CONVERT-HSH-RESPALDO", build_cmd("scripts.Convertir_all", respaldo, "Validar_HSH", "--only", "hsh")) if respaldo else None,
        ]

        for entry in pre_commands:
            if not entry:
                continue
            label, cmd = entry
            rc_pre = yield from _stream_script(label, cmd)
            if rc_pre != 0:
                target_emp = empresa if "RESPALDO" not in label else (respaldo or empresa)
                message = f"Sincronización previa ({label}) falló (rc={rc_pre})."
                yield from _yield_summary(f"{target_emp}: sincronización previa falló ({label})", "error")
                _store_result("ERROR", message)
                yield _result_line({"status": "ERROR", "message": message})
                return
        yield from _yield_summary("Datos locales sincronizados", "success")

    # Ejecución principal del script
    for target_empresa, target_respaldo, target_server in run_targets:
        accion = "Insertando" if aplicar else "Generando reporte"
        yield f"{accion} para empresa {target_empresa} (servidor {target_server})...\n"
        yield from _yield_summary(f"{target_empresa}: {accion.lower()} en curso")

        if target_empresa:
            apply_import_servers.setdefault(target_empresa.upper(), target_server)
            if target_server:
                hsh_servers_used.setdefault(target_empresa.upper(), target_server)

        cmd = build_cmd("scripts.hsh_crear_tag", target_empresa, "--input", archivo_path)
        if target_respaldo:
            cmd += ["--respaldo", target_respaldo]
        if aplicar:
            cmd += ["--apply", "--server", target_server, "--skip-backup-insert"]

        rc = yield from _stream_script(f"CREAR-{target_empresa}", cmd)
        if rc != 0:
            message = f"El script hsh_crear_tag para {target_empresa} finalizó con errores (rc={rc})."
            files = sorted(report_paths | info_paths)
            yield from _yield_summary(f"{target_empresa}: {accion.lower()} falló", "error")
            _store_result("ERROR", message, files=files)
            yield _result_line({"status": "ERROR", "message": message, "files": files})
            return
        yield from _yield_summary(f"{target_empresa}: {accion.lower()} completado", "success")

    verification_messages: list[str] = []
    verification_summary: list[str] = []
    verification_failed = False

    if aplicar and any(inserted_keys_full.values()):
        yield "Iniciando verificación post-aplicación...\n"
        yield from _yield_summary(f"{empresa}: iniciando verificación post-aplicación")
        for emp in sorted(inserted_keys_full.keys()):
            keys_set = inserted_keys_full.get(emp, set())
            if not keys_set:
                continue

            server_for_emp = apply_import_servers.get(emp) or SERVER_RESOLVER.generar_server(emp, "CC")
            if not server_for_emp:
                msg = f"{emp}: no se pudo determinar servidor para verificación."
                verification_messages.append(msg)
                _record_status(emp, "import", False, msg)
                verification_failed = True
                continue

            cmd_import_hsh = build_cmd("scripts.importar_all", server_for_emp, emp, "hsh", "--usecase", "hsh_crear_tag")
            rc_import = yield from _stream_script(f"VER-IMPORT-{emp}", cmd_import_hsh)
            if rc_import != 0:
                msg = f"{emp}: importación HSH falló (rc={rc_import})."
                verification_messages.append(msg)
                _record_status(emp, "import", False, msg)
                verification_failed = True
                yield from _yield_summary(msg, "error")
                continue
            else:
                msg = f"{emp}: importación HSH completada."
                verification_messages.append(msg)
                _record_status(emp, "import", True, msg)
                yield from _yield_summary(msg, "success")

            cmd_convert_hsh = build_cmd("scripts.Convertir_all", emp, "Validar_HSH", "--only", "hsh")
            rc_convert = yield from _stream_script(f"VER-CONVERT-{emp}", cmd_convert_hsh)
            if rc_convert != 0:
                msg = f"{emp}: conversión HSH falló (rc={rc_convert})."
                verification_messages.append(msg)
                _record_status(emp, "convert", False, msg)
                verification_failed = True
                yield from _yield_summary(msg, "error")
                continue
            else:
                msg = f"{emp}: conversión HSH completada."
                verification_messages.append(msg)
                _record_status(emp, "convert", True, msg)
                yield from _yield_summary(msg, "success")

            present, missing = _check_local_keys(emp, keys_set)
            if missing:
                msg = f"{emp}: faltan en LookupTables -> {', '.join(missing)}"
                verification_messages.append(msg)
                _record_status(emp, "lookup", False, msg)
                verification_failed = True
                yield from _yield_summary(msg, "warning")
            else:
                msg = f"{emp}: LookupTables actualizadas para {len(present)} claves."
                verification_messages.append(msg)
                _record_status(emp, "lookup", True, msg)
                yield from _yield_summary(msg, "success")

        scada_lines, scada_failed = _apply_scada_updates_for_web()
        if scada_lines:
            verification_messages.extend(scada_lines)
        if not scada_lines and inserted_keys_map:
            _record_status(empresa, "scada", False, "No se ejecutaron actualizaciones SCADA.")
            verification_failed = True
        if scada_failed:
            verification_failed = True
        if inserted_keys_map:
            if scada_lines:
                scada_msg = "SCADA: actualizaciones completadas." if not scada_failed else "SCADA: se detectaron errores."
                yield from _yield_summary(scada_msg, "error" if scada_failed else "success")
            else:
                yield from _yield_summary("SCADA: no se ejecutaron actualizaciones.", "warning")

        tags_for_pi = inserted_tags_full.get(empresa, set())
        pi_lines, pi_failed, pi_result = _collect_pi_verification(tags_for_pi)
        for line in pi_lines:
            yield line + "\n"
            verification_messages.append(line)
        if pi_failed:
            verification_failed = True
        if tags_for_pi:
            pi_msg = "PI: consulta completada." if not pi_failed else "PI: consulta con errores."
            yield from _yield_summary(pi_msg, "error" if pi_failed else "success")
        if pi_result and report_excel_path:
            try:
                _update_pi_sheet(report_excel_path, pi_result, inserted_tags_full, inserted_pairs_map)
            except Exception as exc:
                msg = f"PI: no se pudo actualizar la hoja PI ({exc})"
                verification_messages.append(msg)

        verification_summary = _build_verification_summary()
        if verification_summary:
            verification_messages.extend(verification_summary)

        extra_messages.extend(verification_messages)

    normalized_files: list[str] = []
    for raw_path in report_paths | info_paths | extra_paths:
        if not raw_path:
            continue
        norm = os.path.normpath(raw_path)
        normalized_files.append(norm)
        if report_excel_path is None and norm.lower().endswith("reporte_crear_tag.xlsx"):
            report_excel_path = norm
    files = sorted(set(normalized_files))

    if not report_excel_path:
        candidate = os.path.normpath(CREAR_TAG_REPORT)
        if os.path.isfile(candidate):
            report_excel_path = candidate

    final_status = "SUCCESS"
    final_message = "Proceso de creación de tags completado."
    if verification_failed:
        final_status = "ERROR"
        final_message = "Proceso completado con errores durante la verificación."

    payload = {
        "status": final_status,
        "message": final_message,
        "files": files,
        "details": extra_messages,
    }
    extra_payload: dict[str, Any] = {"details": extra_messages}
    if report_excel_path:
        extra_payload["report_path"] = report_excel_path
    if verification_summary:
        extra_payload["verification_summary"] = verification_summary
    extra_payload["verification_failed"] = verification_failed
    yield from _yield_summary(final_message, "success" if final_status == "SUCCESS" else "error")
    _store_result(final_status, payload["message"], files=files, extra=extra_payload)
    yield _result_line(payload)


def get_last_crear_result() -> CrearResult | None:
    return last_crear_result


def load_crear_result_preview(sheet: str | None = None, limit: int = 500) -> dict[str, Any] | None:
    result = last_crear_result
    if result is None:
        return None

    report_path = result.extra.get("report_path") if isinstance(result.extra, dict) else None
    if report_path:
        report_path = os.path.normpath(report_path)
        if not os.path.isabs(report_path):
            report_path = os.path.normpath(os.path.join(AUTOADA_DIR, report_path))
    if not report_path or not os.path.isfile(report_path):
        fallback = os.path.normpath(CREAR_TAG_REPORT)
        report_path = fallback if os.path.isfile(fallback) else None

    base_payload: dict[str, Any] = {
        "status": result.status,
        "message": result.message,
        "files": result.files,
        "details": result.extra.get("details", []) if isinstance(result.extra, dict) else [],
        "verification_summary": result.extra.get("verification_summary", []) if isinstance(result.extra, dict) else [],
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

    workbook = load_workbook(report_path, read_only=True, data_only=True)
    try:
        sheet_names = list(workbook.sheetnames)
        if not sheet_names:
            return base_payload

        active_sheet = sheet if sheet in sheet_names else sheet_names[0]
        worksheet = workbook[active_sheet]
        rows_iter = worksheet.iter_rows(values_only=True)

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

        download_url = f"/hsh/crear/result/download?path={quote(report_path)}"

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
        workbook.close()


class _DummyApp:
    def __init__(self, env_map: dict[str, str], base_dir: str) -> None:
        self._env_map = env_map
        self.base_dir = base_dir

    def secure_env(self) -> dict[str, str]:
        return self._env_map
