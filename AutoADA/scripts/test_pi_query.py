import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import paramiko


def _add_project_paths() -> None:
    """Ensure repository root and scripts/ are on sys.path."""
    scripts_dir = Path(__file__).resolve().parent
    root_dir = scripts_dir.parent
    for candidate in (scripts_dir, root_dir):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.append(candidate_str)


_add_project_paths()


from scripts import _Logger as Logger  # type: ignore
from scripts.functions import sshserver  # type: ignore
from scripts.vault_manager import (
    load_vault_from_credentials,
    resolve_named_vault_path,
)
from scripts.import_base import company_prefixes  # type: ignore

# Hosts y servidores PI disponibles en la aplicación
PI_HOST_MAP = {
    "ITCO": ["itco1his01", "itco1his02"],
    "TRA": ["tra1his01", "tra1his02"],
}

PI_SERVER_MAP = {
    "ITCO": "PI-CO-ITCOTRA01",
    "TRA": "PI-CO-ITCOTRA01",
}


def build_env_from_vault(vault: dict) -> dict:
    env = {}
    mapping = {
        "ssh_user": "SSH_USER",
        "ssh_key_pem": "SSH_KEY_PEM",
        "ssh_key_passphrase": "SSH_KEY_PASSPHRASE",
        "ssh_port": "SSH_PORT",
        "user_pi": "USER_PI",
        "pass_pi": "PASS_PI",
    }
    for key, env_key in mapping.items():
        if key in vault and vault[key]:
            env[env_key] = str(vault[key])
    # Hosts opcionales
    if "sca_hosts" in vault:
        sca = vault["sca_hosts"]
        env["SCA_HOSTS"] = ",".join(sca) if isinstance(sca, (list, tuple)) else str(sca)
    if "his_hosts" in vault:
        his = vault["his_hosts"]
        env["HIS_HOSTS"] = ",".join(his) if isinstance(his, (list, tuple)) else str(his)
    return env


def _derive_prefixes(empresa: str, hint: Optional[str]) -> List[str]:
    prefixes: List[str] = []
    if hint:
        lowered = hint.lower()
        cut = None
        for marker in ("sca", "qds", "his"):
            if marker in lowered:
                cut = lowered.index(marker)
                break
        prefixes.append(hint[:cut] if cut is not None else hint)
    for prefix in company_prefixes(empresa) or []:
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
    return [p for p in prefixes if p]


def run_pi_query(
    empresa: str,
    tag_filters: List[str],
    logger_path: Path,
    server_hint: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> None:
    empresa_upper = empresa.upper()
    prefixes = _derive_prefixes(empresa_upper, server_hint)
    if not prefixes:
        raise RuntimeError(f"No se pudieron derivar prefijos SCADA/HIS para {empresa_upper}")

    pi_server = PI_SERVER_MAP.get(empresa_upper, "PI-CO-ITCOTRA01")
    env = os.environ
    pi_user = env.get("USER_PI")
    pi_pass = env.get("PASS_PI")
    if not pi_user or not pi_pass:
        raise RuntimeError("USER_PI/PASS_PI no están definidos en las variables de entorno.")

    pi_user_ps = pi_user.replace('"', '`"')
    pi_pass_ps = pi_pass.replace('"', '`"')

    def _encoded_ps_single(tag: str) -> str:
        tag_json = json.dumps(tag)
        ps_script = f"""
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
foreach ($piPoint in [OSIsoft.AF.PI.PIPoint]::FindPIPoints($piServer, "{empresa_upper}*SCADA*", $true)) {{
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
        encoded = base64.b64encode(ps_script.encode("utf-16-le")).decode("utf-8")
        return f"powershell -NoLogo -NonInteractive -EncodedCommand {encoded}"

    log_dir = logger_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    logger, logger_console = Logger.initlog(str(logger_path))

    aggregated_rows: List[Dict[str, str]] = []
    missing_tags: List[str] = []
    tag_errors: Dict[str, str] = {}

    def _normalize_rows(rows: object) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        if isinstance(rows, list):
            for item in rows:
                if isinstance(item, dict):
                    normalized.append({
                        "Name": str(item.get("Name", item.get("name", "?"))),
                        "Value": str(item.get("Value", item.get("value", ""))),
                        "Timestamp": str(item.get("Timestamp", item.get("timestamp", ""))),
                    })
                else:
                    normalized.append({
                        "Name": str(item),
                        "Value": "",
                        "Timestamp": "",
                    })
        elif isinstance(rows, dict):
            normalized.append({
                "Name": str(rows.get("Name", rows.get("name", "?"))),
                "Value": str(rows.get("Value", rows.get("value", ""))),
                "Timestamp": str(rows.get("Timestamp", rows.get("timestamp", ""))),
            })
        elif rows is not None:
            normalized.append({
                "Name": str(rows),
                "Value": "",
                "Timestamp": "",
            })
        return normalized

    for tag in tag_filters:
        tag_rows: Optional[List[Dict[str, str]]] = None
        last_error = None

        for prefix in prefixes:
            for sca_suffix in ("sca01", "sca02"):
                sca_host = f"{prefix}{sca_suffix}"
                print(f"[PI] Conectando a SCADA {sca_host} para {tag} ...")
                client_sca = None
                try:
                    client_sca = sshserver(sca_host, logger, logger_console)
                    if client_sca is None:
                        last_error = "sshserver devolvió None"
                        print(f"[PI] Error conectando a {sca_host}: {last_error}")
                        continue
                    transport = client_sca.get_transport()
                    if transport is None or not transport.is_active():
                        last_error = "transporte SCADA inactivo"
                        print(f"[PI] {sca_host}: transporte SSH inactivo")
                        continue
                    for his_suffix in ("his01", "his02"):
                        his_host = f"{prefix}{his_suffix}"
                        print(f"[PI]   Túnel a {his_host} para {tag} ...")
                        channel = None
                        client_his = None
                        try:
                            channel = transport.open_channel(
                                "direct-tcpip",
                                (his_host, 22),
                                ("127.0.0.1", 0),
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
                            command = _encoded_ps_single(tag)
                            Logger.write_log().log_all('info', f'CI: comando {command}', logger_console, logger)
                            stdin, stdout, stderr = client_his.exec_command(command)
                            output = stdout.read().decode("utf-8", "ignore")
                            err_output = stderr.read().decode("utf-8", "ignore").strip()
                            if err_output:
                                print(f"[PI] STDERR ({his_host}): {err_output}")
                            marker = "__PI_JSON__:"
                            idx = output.find(marker)
                            if idx == -1:
                                last_error = output.strip() or "salida sin marcador JSON"
                                print(f"[PI] {his_host}: respuesta inesperada -> {last_error[:200]}")
                                continue
                            json_text = output[idx + len(marker):].strip()
                            raw_rows = json.loads(json_text) if json_text else []
                            rows = _normalize_rows(raw_rows)
                            if rows:
                                tag_rows = rows
                                aggregated_rows.extend(rows)
                                print(f"[PI] {his_host}: {len(rows)} valores recuperados para {tag}")
                                break
                            last_error = "sin valores"
                            print(f"[PI] {his_host}: sin valores para {tag}")
                        except Exception as exc:
                            last_error = str(exc)
                            print(f"[PI] Error {sca_host}->{his_host} ({tag}): {exc}")
                        finally:
                            if client_his is not None:
                                client_his.close()
                            if channel is not None:
                                channel.close()
                    if tag_rows:
                        break
                except Exception as exc:
                    last_error = str(exc)
                    print(f"[PI] Error conectando a SCADA {sca_host}: {exc}")
                finally:
                    if client_sca is not None:
                        client_sca.close()
                if tag_rows:
                    break
            if tag_rows:
                break

        if not tag_rows:
            missing_tags.append(tag)
            if last_error:
                tag_errors[tag] = last_error
            print(f"[PI] No se obtuvo información para {tag} ({last_error or 'sin datos'})")

    if not aggregated_rows and missing_tags:
        detail = "; ".join(f"{tag}: {tag_errors.get(tag, 'sin datos')}" for tag in missing_tags)
        raise RuntimeError(f"No se pudo obtener información: {detail}")

    if aggregated_rows:
        print("[PI] Resultados:")
        for row in aggregated_rows:
            print(f"  - {row.get('Name', '?')} = {row.get('Value', '?')}")
    else:
        print("[PI] No hubo coincidencias con los tags indicados.")

    if missing_tags:
        print(f"[PI] Tags sin información: {', '.join(missing_tags)}")

    if output_path is not None and aggregated_rows:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(aggregated_rows, fh, ensure_ascii=False, indent=2)
        print(f"[PI] Resultados guardados en {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba de consulta PI usando secure_env.")
    parser.add_argument("--empresa", required=True, choices=list(PI_HOST_MAP.keys()),
                        help="Empresa objetivo (ITCO, TRA).")
    parser.add_argument("--tags", required=True,
                        help="Nombres completos de tags (separados por coma) o prefijos SCADA_KEY.")
    parser.add_argument("--primary-host", default=None,
                        help="Host HIS base (ej: itco1his01) para derivar prefijos.")
    parser.add_argument("--vault-user", required=True, help="Usuario para abrir el vault.")
    parser.add_argument("--vault-pass", required=True, help="Password del vault.")
    parser.add_argument("--vault-file", default=None,
                        help="Archivo de vault (por defecto usa scripts/vault.bin).")
    parser.add_argument("--log", default="out/log/pi_query_test.log",
                        help="Archivo donde dejar el log detallado (por defecto out/log/pi_query_test.log).")
    parser.add_argument("--output", default=None,
                        help="Archivo donde guardar en JSON los resultados de la consulta.")
    args = parser.parse_args()

    vault_path = resolve_named_vault_path(args.vault_file) if args.vault_file else None
    vault = load_vault_from_credentials(args.vault_user, args.vault_pass, vault_path=vault_path)

    env_updates = build_env_from_vault(vault)
    previous_env = {k: os.environ.get(k) for k in env_updates}
    os.environ.update(env_updates)

    try:
        tag_filters = [value.strip() for value in args.tags.split(",") if value.strip()]
        if not tag_filters:
            raise ValueError("Debes indicar al menos un tag en --tags")
        output_path = Path(args.output) if args.output else None
        run_pi_query(
            args.empresa,
            tag_filters,
            Path(args.log),
            server_hint=args.primary_host,
            output_path=output_path,
        )
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
