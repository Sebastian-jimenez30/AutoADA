from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import paramiko

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUX_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
AUTOADA_DIR = os.path.join(AUX_ROOT, "AutoADA")
SCRIPTS_DIR = os.path.join(AUTOADA_DIR, "scripts")

if AUTOADA_DIR not in os.sys.path:
  os.sys.path.insert(0, AUTOADA_DIR)
if SCRIPTS_DIR not in os.sys.path:
  os.sys.path.insert(0, SCRIPTS_DIR)

from scripts import _Logger as Logger  # type: ignore
from scripts.functions import scada_online, sshserver  # type: ignore
from scripts.import_base import company_prefixes  # type: ignore

SCADA_HOSTS_FULL: Dict[str, list[str]] = {
  "ITCO": ["itco1sca01", "itco1sca02", "itco1qds01"],
  "TRA": ["tra1sca01", "tra1sca02", "tra1qds01"],
  "REPS": ["rep1sca01", "rep1sca02", "rep1qds01"],
  "REPP": ["rep2sca01", "rep2sca02", "rep2qds01"],
}

PI_SERVER_MAP_DEFAULT: Dict[str, str] = {
  "ITCO": "PI-CO-ITCOTRA01",
  "TRA": "PI-CO-ITCOTRA01",
  "REPS": "PI-PE-REPCTM01",
  "REPP": "PI-PE-REPCTM01",
}


@dataclass
class PiSnapshotResult:
  lines: List[str]
  missing_lines: List[str]
  messages: List[str]
  snapshot_map: Dict[str, List[Dict[str, str]]]
  missing_map: Dict[str, List[str]]
  collected_at: Optional[str]
  has_failures: bool


def apply_scada_updates(
  *,
  inserted_keys_map: dict[str, dict[str, set[str]]],
  env: dict[str, str],
  autoada_dir: str,
  enable: bool = True,
  log_filename: str = "scada_crear_tag.log",
  record_status: Optional[Callable[[str, str, Optional[bool], Optional[str]], None]] = None,
) -> tuple[list[str], bool]:
  """
  Aplica actualizaciones SCADA (encendido/apagado de bits) reutilizable para crear/eliminar/cambiar.
  """
  if not inserted_keys_map:
    return [], False

  if sshserver is None:
    msg = "SCADA: función sshserver no disponible."
    if record_status:
      for emp in inserted_keys_map.keys():
        record_status(emp, "scada", False, msg)
    return [msg], True

  prev_env = {k: os.environ.get(k) for k in env}
  os.environ.update(env)

  log_dir = Path(autoada_dir) / "out" / "log"
  log_dir.mkdir(parents=True, exist_ok=True)

  if Logger is None:
    msg = "SCADA: Logger no disponible."
    if record_status:
      for emp in inserted_keys_map.keys():
        record_status(emp, "scada", False, msg)
    for key, value in prev_env.items():
      if value is None:
        os.environ.pop(key, None)
      else:
        os.environ[key] = value
    return [msg], True

  try:
    logger, logger_console = Logger.initlog(str(log_dir / log_filename))
  except Exception as exc:
    msg = f"SCADA: no se pudo inicializar logger ({exc})."
    if record_status:
      for emp in inserted_keys_map.keys():
        record_status(emp, "scada", False, msg)
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
          for host in sorted(domain_hosts.get(dom, set())):
            label = f"{emp_u} ({host})"
            client = sshserver(host, logger, logger_console)
            if client is None:
              raise RuntimeError("sshserver devolvió None")
            record_status and record_status(emp_u, "scada", None, f"Conexión establecida con {host}")
            host_online = None
            try:
              host_online = scada_online(client, logger, logger_console)
            except Exception as exc:
              messages.append(f"{label}: error verificando estado ONLINE ({exc})")
            if host_online:
              messages.append(f"{label}: estado ONLINE detectado ({host_online})")

            try:
              for base_key, suffixes in base_map.items():
                suffix_set = {s.upper() for s in suffixes if s}
                bit_specs: set[tuple[int, int]] = set()
                if suffix_set & analog_suffixes:
                  if "ESTIMATED" in suffix_set:
                    bit_specs.add((5, 2))
                  else:
                    bit_specs.add((5, 1))
                else:
                  bit_specs.add((4, 1))
                if not bit_specs:
                  bit_specs.add((4, 1))

                for tipo, bit in sorted(bit_specs):
                  valor = 1 if enable else 0
                  cmd = f". ~/.bash_profile && dbset -k 10 {tipo} 12 {base_key} {bit} = {valor}"
                  try:
                    stdin, stdout, stderr = client.exec_command(cmd)
                    rc_cmd = stdout.channel.recv_exit_status()
                    if rc_cmd == 0:
                      msg = f"{label}: OK {base_key} bit {bit}"
                      messages.append(msg)
                      record_status and record_status(emp_u, "scada", True, msg)
                    else:
                      err = stderr.read().decode("utf-8", "ignore").strip()
                      msg = f"{label}: fallo {base_key} bit {bit} (rc={rc_cmd}) {err}"
                      messages.append(msg)
                      record_status and record_status(emp_u, "scada", False, msg)
                      has_fail = True
                  except Exception as exc:
                    msg = f"{label}: error {base_key} bit {bit}: {exc}"
                    messages.append(msg)
                    record_status and record_status(emp_u, "scada", False, msg)
                    has_fail = True
            finally:
              try:
                client.close()
              except Exception:
                pass
        except Exception as exc:
          messages.append(f"{emp_u}: error conectando a SCADA ({exc})")
          record_status and record_status(emp_u, "scada", False, str(exc))
          has_fail = True
  finally:
    for key, value in prev_env.items():
      if value is None:
        os.environ.pop(key, None)
      else:
        os.environ[key] = value

  return messages, has_fail


def collect_pi_snapshots(
  *,
  env_map: dict[str, str],
  base_dir: str,
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
  pi_server_map = pi_server_map or PI_SERVER_MAP_DEFAULT

  lines: List[str] = []
  missing_lines: List[str] = []
  messages: List[str] = []
  snapshot_map: Dict[str, List[Dict[str, str]]] = {}
  missing_map: Dict[str, List[str]] = {}
  collected_at: Optional[str] = None
  has_failures = False

  env_pi = env_map or {}
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
        record_status and record_status(emp_u, "pi", False, msg)
      return PiSnapshotResult(lines, missing_lines, messages, snapshot_map, missing_map, collected_at, True)

    pi_user_ps = pi_user.replace('"', '`"')
    pi_pass_ps = pi_pass.replace('"', '`"')
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_dir = Path(base_dir) / "out" / "log"
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
      allowed: set[str] = set()
      for host in SCADA_HOSTS_FULL.get(emp_u, []) or []:
        for pref in _derive_prefixes_from_hint(host):
          if pref:
            allowed.add(pref)
      if hint:
        for pref in _derive_prefixes_from_hint(hint):
          if pref and (not allowed or pref in allowed):
            prefixes.append(pref)
      for pref in sorted(allowed):
        if pref not in prefixes:
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
$piPoint = $null
try {{
    $piPoint = [OSIsoft.AF.PI.PIPoint]::FindPIPoint($piServer, $target)
}} catch {{}}
if (-not $piPoint) {{
    $candidates = [OSIsoft.AF.PI.PIPoint]::FindPIPoints($piServer, "*${{target}}*", $true)
    foreach ($p in $candidates) {{
        $piPoint = $p
        break
    }}
}}
if ($piPoint -ne $null) {{
    $cv = $piPoint.CurrentValue()
    $result += [PSCustomObject]@{{
        Name = $piPoint.Name
        Value = $cv.Value.ToString()
        Timestamp = $cv.Timestamp.ToString()
    }}
}}
"__PI_JSON__:" + ($result | ConvertTo-Json -Depth 4 -Compress)
"""
      ps_script = template.format(
        pi_server=pi_server,
        pi_pass_ps=pi_pass_ps,
        pi_user_ps=pi_user_ps,
        tag_json=tag_json,
      )
      encoded = base64.b64encode(ps_script.encode("utf-16-le")).decode("utf-8")
      return f"powershell -NoLogo -NonInteractive -EncodedCommand {encoded}"

    def _encoded_ps_batch(emp_u: str, tags: list[str], pi_server: str) -> str:
      tags_json = json.dumps(tags)
      template = """
$ErrorActionPreference = 'Stop'
Add-Type -Path "C:\\Program Files (x86)\\PIPC\\AF\\PublicAssemblies\\4.0\\OSIsoft.AFSDK.dll"
$piServers = [OSIsoft.AF.PI.PIServers]::GetPIServers()
$piServer = $piServers['{pi_server}']
$securePassword = ConvertTo-SecureString "{pi_pass_ps}" -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential("{pi_user_ps}", $securePassword)
$piServer.Connect($credential)
$targets = ConvertFrom-Json @'
{tags_json}
'@
$result = @{{}}
foreach ($target in $targets) {{
    $hits = @()
    $piPoint = $null
    try {{
        $piPoint = [OSIsoft.AF.PI.PIPoint]::FindPIPoint($piServer, $target)
    }} catch {{}}
    if (-not $piPoint) {{
        $candidates = [OSIsoft.AF.PI.PIPoint]::FindPIPoints($piServer, "*${{target}}*", $true)
        foreach ($p in $candidates) {{
            $piPoint = $p
            break
        }}
    }}
    if ($piPoint -ne $null) {{
        $cv = $piPoint.CurrentValue()
        $hits += [PSCustomObject]@{{
            Name = $piPoint.Name
            Value = $cv.Value.ToString()
            Timestamp = $cv.Timestamp.ToString()
        }}
    }}
    $result[$target] = $hits
}}
"__PI_JSON__:" + ($result | ConvertTo-Json -Depth 4 -Compress)
"""
      ps_script = template.format(
        pi_server=pi_server,
        pi_pass_ps=pi_pass_ps,
        pi_user_ps=pi_user_ps,
        tags_json=tags_json,
      )
      encoded = base64.b64encode(ps_script.encode("utf-16-le")).decode("utf-8")
      return f"powershell -NoLogo -NonInteractive -EncodedCommand {encoded}"

    def _record(emp: str, message: str, ok: Optional[bool]) -> None:
      if record_status:
        record_status(emp, "pi", ok, message)

    def _safe_int(value: str | None, default: int) -> int:
      try:
        return int(str(value).strip())
      except Exception:
        return default

    pi_max_attempts_per_tag = max(1, _safe_int(os.environ.get("PI_TAG_MAX_ATTEMPTS"), 2))
    pi_command_timeout_s = max(3, _safe_int(os.environ.get("PI_COMMAND_TIMEOUT_S"), 20))
    pi_connect_timeout_s = max(3, _safe_int(os.environ.get("PI_CONNECT_TIMEOUT_S"), 10))
    pi_tunnel_timeout_s = max(3, _safe_int(os.environ.get("PI_TUNNEL_TIMEOUT_S"), 10))
    scada_stat_timeout_s = max(3, _safe_int(os.environ.get("SCADA_STAT_TIMEOUT_S"), 8))

    online_scada_cache: dict[str, str | None] = {}

    def _exec_command_with_timeout(
      client: paramiko.SSHClient,
      command: str,
      timeout_s: int,
    ) -> tuple[str, str, bool]:
      transport = client.get_transport()
      if transport is None or not transport.is_active():
        return "", "SSH transport inactivo", True
      channel = transport.open_session()
      channel.settimeout(1.0)
      stdout_chunks: list[str] = []
      stderr_chunks: list[str] = []
      timed_out = False
      start = time.monotonic()
      try:
        channel.exec_command(command)
        while True:
          if channel.recv_ready():
            stdout_chunks.append(channel.recv(65536).decode("utf-8", "ignore"))
          if channel.recv_stderr_ready():
            stderr_chunks.append(channel.recv_stderr(65536).decode("utf-8", "ignore"))
          if channel.exit_status_ready():
            while channel.recv_ready():
              stdout_chunks.append(channel.recv(65536).decode("utf-8", "ignore"))
            while channel.recv_stderr_ready():
              stderr_chunks.append(channel.recv_stderr(65536).decode("utf-8", "ignore"))
            break
          if time.monotonic() - start > float(timeout_s):
            timed_out = True
            break
          time.sleep(0.1)
      finally:
        try:
          channel.close()
        except Exception:
          pass
      return "".join(stdout_chunks), "".join(stderr_chunks).strip(), timed_out

    def _parse_online_scada(output: str) -> str | None:
      for line in (output or "").splitlines():
        if "Status: ONLINE" in line and "Source" in line:
          try:
            server_part = line.split(":")[1]
            online_server = server_part.split("Status")[0].strip()
            return online_server or None
          except Exception:
            continue
      return None

    def _resolve_online_scada(prefix: str) -> str | None:
      if prefix in online_scada_cache:
        return online_scada_cache[prefix]

      online_host: str | None = None
      last_err: str | None = None
      for sca_suffix in ("sca01", "sca02"):
        sca_host = f"{prefix}{sca_suffix}"
        client = None
        try:
          client = sshserver(sca_host, logger, logger_console)
          if client is None:
            last_err = f"{sca_host}: sshserver devolvio None"
            continue
          stdout, stderr, timed_out = _exec_command_with_timeout(
            client,
            ". ~/.bash_profile && dbstat 10",
            scada_stat_timeout_s,
          )
          if timed_out:
            last_err = f"{sca_host}: dbstat timeout"
            continue
          if stderr:
            last_err = f"{sca_host}: {stderr}"
          online = _parse_online_scada(stdout)
          if online:
            online_host = online
            break
        except Exception as exc:
          last_err = str(exc)
        finally:
          try:
            if client is not None:
              client.close()
          except Exception:
            pass

      if online_host is None and last_err:
        console_write(f"[PI] No se pudo determinar SCADA online para {prefix} ({last_err})", "warn")
      online_scada_cache[prefix] = online_host
      return online_host

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

      tag_rows_map: Dict[str, Optional[List[Dict[str, str]]]] = {t: None for t in tag_list}
      tag_last_error: Dict[str, Optional[str]] = {t: None for t in tag_list}
      attempts_map: Dict[str, int] = {t: 0 for t in tag_list}

      for prefix in prefixes:
        remaining = [t for t in tag_list if tag_rows_map[t] is None and attempts_map[t] < pi_max_attempts_per_tag]
        if not remaining:
          break

        sca_host = _resolve_online_scada(prefix)
        if not sca_host:
          for t in remaining:
            tag_last_error[t] = "no se detectó SCADA ONLINE"
            _record(emp_u, f"{t}: prefijo {prefix} sin SCADA ONLINE", None)
          console_write(f"[PI] {emp_u}: prefijo {prefix} sin SCADA ONLINE", "warn")
          continue

        console_write(f"[PI] Conectando a SCADA {sca_host} ...", "info")
        client_sca = None
        try:
          client_sca = sshserver(sca_host, logger, logger_console)
        except Exception as exc:
          for t in remaining:
            tag_last_error[t] = str(exc)
            _record(emp_u, f"{t}: error conectando a {sca_host}: {exc}", None)
          console_write(f"[PI] Error conectando a SCADA {sca_host}: {exc}", "error")
          continue

        if client_sca is None:
          for t in remaining:
            tag_last_error[t] = "sshserver devolvió None"
            _record(emp_u, f"{t}: {sca_host} sshserver devolvió None", None)
          console_write(f"[PI] {sca_host}: sshserver devolvió None", "error")
          continue

        transport = client_sca.get_transport()
        if transport is None or not transport.is_active():
          for t in remaining:
            tag_last_error[t] = "transporte SSH inactivo"
            _record(emp_u, f"{t}: {sca_host} transporte SSH inactivo", None)
          console_write(f"[PI] {sca_host}: transporte SSH inactivo", "error")
          try:
            client_sca.close()
          except Exception:
            pass
          continue

        try:
          for his_suffix in ("his01", "his02"):
            tags_pending = [
              t for t in tag_list if tag_rows_map[t] is None and attempts_map[t] < pi_max_attempts_per_tag
            ]
            if not tags_pending:
              break

            his_host = f"{prefix}{his_suffix}"
            channel = None
            client_his = None
            try:
              console_write(
                f"[PI]   Tunel a {his_host} (tags={len(tags_pending)}, intento {attempts_map[tags_pending[0]] + 1}/{pi_max_attempts_per_tag}) ...",
                "info",
              )
              channel = transport.open_channel(
                "direct-tcpip",
                (his_host, 22),
                ("127.0.0.1", 0),
                timeout=pi_tunnel_timeout_s,
              )
              client_his = paramiko.SSHClient()
              client_his.set_missing_host_key_policy(paramiko.AutoAddPolicy())
              client_his.connect(
                hostname=his_host,
                username=pi_user,
                password=pi_pass,
                sock=channel,
                look_for_keys=False,
                allow_agent=False,
                timeout=pi_connect_timeout_s,
                auth_timeout=pi_connect_timeout_s,
                banner_timeout=pi_connect_timeout_s,
              )

              command = _encoded_ps_batch(emp_u, tags_pending, pi_server)
              if Logger is not None and logger is not None:
                Logger.write_log().log_all("info", f"[PI] comando {command}", logger_console, logger)

              output, err_output, timed_out = _exec_command_with_timeout(
                client_his,
                command,
                pi_command_timeout_s,
              )
              for t in tags_pending:
                attempts_map[t] += 1
              if timed_out:
                for t in tags_pending:
                  tag_last_error[t] = f"timeout ({pi_command_timeout_s}s)"
                  _record(emp_u, f"{t}: {his_host} timeout", None)
                console_write(f"[PI] {his_host}: timeout consultando tags ({len(tags_pending)})", "warn")
                continue

              if err_output:
                console_write(f"[PI] {his_host} STDERR: {err_output}", "warn")
                # Fallback a consultas individuales si el batch falla por StreamQuery/ObjectDisposed
                if "StreamQuery" in err_output or "ObjectDisposed" in err_output:
                  for t in list(tags_pending):
                    try:
                      cmd_single = _encoded_ps_single(emp_u, t, pi_server)
                      out_single, err_single, to_single = _exec_command_with_timeout(
                        client_his,
                        cmd_single,
                        pi_command_timeout_s,
                      )
                      if to_single:
                        tag_last_error[t] = f"timeout ({pi_command_timeout_s}s)"
                        _record(emp_u, f"{t}: {his_host} timeout (fallback)", None)
                        console_write(f"[PI] {his_host}: timeout consultando {t} (fallback single)", "warn")
                        continue
                      if err_single:
                        tag_last_error[t] = err_single
                        console_write(f"[PI] {his_host}: STDERR fallback {t}: {err_single}", "warn")
                        continue
                      idx_single = out_single.find("__PI_JSON__:")
                      if idx_single == -1:
                        tag_last_error[t] = out_single.strip() or "respuesta inesperada"
                        console_write(f"[PI] {his_host}: respuesta inesperada fallback {t}", "warn")
                        continue
                      raw_obj_single = json.loads(out_single[idx_single + len("__PI_JSON__:") :].strip() or "{}")
                      raw_rows = raw_obj_single if isinstance(raw_obj_single, (list, dict)) else {}
                      normalized_single: List[Dict[str, str]] = []
                      if isinstance(raw_rows, list):
                        for item in raw_rows:
                          if isinstance(item, dict):
                            normalized_single.append(
                              {
                                "Name": str(item.get("Name", item.get("name", "?"))),
                                "Value": str(item.get("Value", item.get("value", ""))),
                                "Timestamp": str(item.get("Timestamp", item.get("timestamp", ""))),
                              }
                            )
                      elif isinstance(raw_rows, dict) and raw_rows:
                        normalized_single.append(
                          {
                            "Name": str(raw_rows.get("Name", raw_rows.get("name", "?"))),
                            "Value": str(raw_rows.get("Value", raw_rows.get("value", ""))),
                            "Timestamp": str(raw_rows.get("Timestamp", raw_rows.get("timestamp", ""))),
                          }
                        )
                      if normalized_single:
                        tag_rows_map[t] = normalized_single
                        aggregated_rows.extend(normalized_single)
                        console_write(f"[PI] {his_host}: valores (fallback) para {t}", "info")
                      else:
                        tag_last_error[t] = "sin valores"
                    except Exception as exc_fallback:
                      tag_last_error[t] = str(exc_fallback)
                      _record(emp_u, f"{t}: error fallback {his_host}: {exc_fallback}", None)
                  continue

              marker = "__PI_JSON__:"
              idx = output.find(marker)
              if idx == -1:
                for t in tags_pending:
                  tag_last_error[t] = err_output or output.strip() or "respuesta inesperada"
                  _record(emp_u, f"{t}: {his_host} respuesta inesperada", None)
                console_write(f"[PI] {his_host}: respuesta inesperada -> {err_output or output.strip()}", "warn")
                continue

              json_text = output[idx + len(marker) :].strip()
              raw_obj = json.loads(json_text) if json_text else {}

              for t in tags_pending:
                raw_rows = raw_obj.get(t, [])
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
                  tag_rows_map[t] = normalized
                  aggregated_rows.extend(normalized)
                  _record(emp_u, f"{t}: {len(normalized)} valores desde {his_host}", None)
                  console_write(f"[PI] {his_host}: valores capturados para {t}", "info")
                else:
                  tag_last_error[t] = "sin valores"
                  console_write(f"[PI] {his_host}: sin valores para {t}", "warn")

            except Exception as exc:
              for t in tags_pending:
                attempts_map[t] += 1
                tag_last_error[t] = str(exc)
                _record(emp_u, f"{t}: error {sca_host}->{his_host}: {exc}", None)
              console_write(f"[PI] Error {sca_host}->{his_host}: {exc}", "error")
            finally:
              if client_his is not None:
                client_his.close()
              if channel is not None:
                channel.close()
        finally:
          try:
            if client_sca is not None:
              client_sca.close()
          except Exception:
            pass

      for tag in tag_list:
        if tag_rows_map[tag] is None:
          missing_tags.append(tag)
          has_failures = True
          warning = f"{emp_u}:{tag}:{tag_last_error.get(tag) or 'sin datos'}"
          missing_lines.append(warning)
          console_write(
            f"[PI] {emp_u}: no se obtuvo informacion para {tag} ({tag_last_error.get(tag) or 'sin datos'})", "warn"
          )
          _record(emp_u, f"{tag}: {tag_last_error.get(tag) or 'sin datos'}", False)
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
