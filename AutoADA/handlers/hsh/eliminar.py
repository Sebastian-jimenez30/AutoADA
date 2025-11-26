from __future__ import annotations

import csv
import json
import os
import re
import pandas as pd
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .common import (
    Logger,
    Workbook,
    build_cmd,
    messagebox,
    show_summary_dialog,
    sshserver,
    scada_online,
    SCADA_HOSTS_FULL,
)
from scripts.hsh_crear_tag import _load_scada_data  # type: ignore
from scripts.hsh_cambiar_key import _determine_scada_action  # type: ignore

def ejecutar_eliminar_tag_hsh(app, aplicar: bool = False, origin: str | None = None):
    """
    Ejecuta el flujo de eliminación HSH/SCADA:
    - Lee el Excel de claves a eliminar
    - Valida coincidencias en lookup_tables y groups
    - Si --apply: elimina en Mongo y genera Delete/Purge + apaga bits SCADA
    - Siempre procesa la empresa principal y la de respaldo por separado
    """

    # ---------- Inputs desde UI ----------
    empresa_var = getattr(app, "opcion_empresa_hsh_eliminar", None)
    if not empresa_var:
        messagebox.showerror("Error", "No se encontró configuración para esta vista.")
        return

    empresa = (empresa_var.get() or "").strip().upper()
    if not empresa or empresa == "Empresa...":
        messagebox.showerror("Error", "Selecciona una empresa.")
        return

    excel_path = getattr(app, "hsh_eliminar_tag_file", None)
    if not excel_path or not os.path.isfile(excel_path):
        messagebox.showerror("Error", "Selecciona el Excel con las claves SCADA a eliminar.")
        return

    dominio = "CC"
    respaldo_map = {"ITCO": "TRA", "TRA": "ITCO", "REPS": "REPP", "REPP": "REPS"}
    respaldo = respaldo_map.get(empresa)
    if not respaldo:
        messagebox.showerror("Error", f"No se encontró respaldo definido para {empresa}.")
        return

    # ---------- Confirmación ----------
    if aplicar and not messagebox.askyesno("Confirmar eliminación",
                                           "¿Eliminar registros en lookup_tables y apagar bits SCADA?",
                                           parent=app.ventana):
        return

    servidor_principal = app.generar_server(empresa, dominio)
    servidor_respaldo = app.generar_server(respaldo, dominio)
    if not servidor_principal or not servidor_respaldo:
        messagebox.showerror("Error", "No se pudieron resolver servidores principal o respaldo.")
        return

    # ---------- Estado UI ----------
    botones = [
        getattr(app, "boton_validar_tag_hsh_eliminar", None),
        getattr(app, "boton_eliminar_tag_hsh", None),
    ]
    botones = [b for b in botones if b]
    for b in botones:
        try:
            b.config(state="disabled")
        except Exception:
            pass

    if getattr(app, "console", None):
        app.console.clear()

    app.start_status("Preparando eliminación HSH/SCADA...", indeterminate=True)

    def _ui(fn):
        try:
            app.ventana.after(0, fn)
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def _console(msg: str, tag: str = "info"):
        console = getattr(app, "console", None)
        if console is not None:
            _ui(lambda: console.write(msg, tag))

    def _set_status(text: str):
        if hasattr(app, "set_status"):
            _ui(lambda: app.set_status(text))

    # ---------- Variables base ----------
    env, cwd = app.secure_env(), app.base_dir
    server_map: dict[str, str] = {empresa: servidor_principal}
    if respaldo:
        server_map[respaldo] = servidor_respaldo
    run_targets: list[tuple[str, str, str]] = [(empresa, respaldo, servidor_principal)]
    if respaldo:
        run_targets.append((respaldo, empresa, servidor_respaldo))
    run_targets = [item for item in run_targets if item[0] and item[2]]

    # ---------- Recolectores ----------
    report_paths: list[str] = []
    delete_files: list[str] = []
    purge_files: list[str] = []
    lookup_deleted: dict[str, int] = {}
    lookup_remaining: dict[str, int] = {}
    lookup_would_delete: dict[str, list[str]] = {}
    lookup_removed: dict[str, list[str]] = {}
    lookup_still: dict[str, list[str]] = {}
    lookup_statuses: defaultdict[str, dict[str, str]] = defaultdict(dict)
    group_matches: defaultdict[str, dict[str, list[dict[str, str]]]] = defaultdict(dict)
    verified_removed: dict[str, list[str]] = {}
    verification_failures: dict[str, list[str]] = {}
    delete_keys_by_emp: defaultdict[str, set[str]] = defaultdict(set)
    scada_actions: list[dict[str, str]] = []

    def _normalize_base_key(value: object) -> str:
        token = str(value or "").strip()
        if not token:
            return ""
        match = re.search(r"\d{5,}", token)
        if match:
            return match.group(0).upper()
        token = token.split("|")[-1]
        token = token.split("->", 1)[0]
        token = token.split(".", 1)[0]
        token = token.split(":", 1)[-1]
        token = token.strip(" -")
        return token.upper()

    def _collect_target_keys() -> Set[str]:
        targets: Set[str] = set()
        for keys in delete_keys_by_emp.values():
            for key in keys:
                cleaned = _normalize_base_key(key)
                if cleaned:
                    targets.add(cleaned)
        return targets

    def _collect_removed_keys() -> Set[str]:
        removed: Set[str] = set()
        for keys in verified_removed.values():
            for key in keys:
                cleaned = _normalize_base_key(key)
                if cleaned:
                    removed.add(cleaned)
        return removed

    def _collect_pending_keys(removed: Set[str]) -> Set[str]:
        pending: Set[str] = set()
        for keys in lookup_still.values():
            for key in keys:
                cleaned = _normalize_base_key(key)
                if cleaned:
                    pending.add(cleaned)
        for keys in verification_failures.values():
            for key in keys:
                cleaned = _normalize_base_key(key)
                if cleaned:
                    pending.add(cleaned)
        targets = _collect_target_keys()
        if targets:
            pending.update(targets - removed)
        return pending

    def _build_eliminar_summary() -> Tuple[str, List[str], List[str]]:
        removed = _collect_removed_keys()
        pending = _collect_pending_keys(removed)
        summary = f"Claves eliminadas: {len(removed)}"
        return summary, sorted(removed), sorted(pending)
    errors: List[str] = []
    completed: List[str] = []

    def _extract_base_keys_from_excel(path: str) -> set[str]:
        try:
            df = pd.read_excel(path, sheet_name="Eliminar Tag", dtype=str)
        except Exception as exc:
            _console(f"[EXCEL] No se pudo leer la hoja 'Eliminar Tag': {exc}", "error")
            return set()
        keys: set[str] = set()
        if df.empty:
            return keys
        for column in df.columns:
            if str(column).strip().upper() in {"SCADA_KEY", "SCADA KEY", "SCADAKEY"}:
                series = df[column].dropna()
                for raw in series.astype(str):
                    value = raw.strip()
                    if not value:
                        continue
                    base = value.split(".", 1)[0].strip().upper()
                    if base:
                        keys.add(base)
        return keys

    base_keys_excel = _extract_base_keys_from_excel(excel_path)
    excel_scada_maps: dict[str, dict[str, set[str]]] = {}
    if base_keys_excel:
        excel_scada_maps[empresa] = {base: set() for base in base_keys_excel}
        if respaldo:
            excel_scada_maps[respaldo] = {base: set() for base in base_keys_excel}

    scada_metadata_cache: dict[str, tuple[dict[str, Dict[str, object]], dict[str, set[str]]]] = {}

    def _get_scada_metadata(emp: str) -> tuple[dict[str, Dict[str, object]], dict[str, set[str]]]:
        emp_u = emp.upper()
        if emp_u in scada_metadata_cache:
            return scada_metadata_cache[emp_u]
        try:
            _, info_by_emp, _ = _load_scada_data(app.base_dir, [emp_u])
        except Exception:
            info_by_emp = {}
        info_emp = info_by_emp.get(emp_u, {}) if isinstance(info_by_emp, dict) else {}
        suffix_map: dict[str, set[str]] = defaultdict(set)
        for variant in info_emp.keys():
            base, dot, suf = variant.partition(".")
            base_u = base.upper()
            if dot and suf:
                suffix_map[base_u].add(suf.strip().upper())
        scada_metadata_cache[emp_u] = (info_emp, suffix_map)
        return scada_metadata_cache[emp_u]

    def _collect_scada_hosts(emp_u: str) -> List[Tuple[str, str]]:
        domain_hosts: Dict[str, Set[str]] = {"CC": set(), "QA": set()}
        for host in SCADA_HOSTS_FULL.get(emp_u, []) or []:
            host = host.strip()
            if not host:
                continue
            domain = "QA" if "qds" in host.lower() else "CC"
            domain_hosts.setdefault(domain, set()).add(host)
        for dom in ("CC", "QA"):
            try:
                host = app.generar_server(emp_u, dom)
            except Exception:
                host = None
            if host:
                domain_hosts.setdefault(dom, set()).add(host)
        entries: List[Tuple[str, str]] = []
        for dom in ("CC", "QA"):
            for host in sorted(domain_hosts.get(dom, set())):
                entries.append((dom, host))
        return entries

    def _apply_scada_dbset(
        emp_u: str,
        base_suffix_map: dict[str, set[str]],
        enable: bool,
        action_label: str,
    ) -> tuple[List[str], bool]:
        updates: List[str] = []
        if not base_suffix_map:
            return updates, False

        env_secure = app.secure_env()
        prev_env = {k: os.environ.get(k) for k in env_secure}
        os.environ.update(env_secure)

        log_dir = Path(app.base_dir) / "out" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger = logger_console = None
        if Logger is not None:
            try:
                log_name = "eliminar_scada_on.log" if enable else "eliminar_scada_off.log"
                logger, logger_console = Logger.initlog(str(log_dir / log_name), append=True)
            except Exception:
                logger = logger_console = None

        has_fail = False
        accion = "Encender" if enable else "Apagar"
        info_emp, scada_suffixes = _get_scada_metadata(emp_u)
        hosts = _collect_scada_hosts(emp_u)
        if not hosts:
            msg = f"[SCADA] {emp_u}: no se encontraron servidores SCADA configurados"
            updates.append(msg)
            has_fail = True
            scada_actions.append({
                "empresa": emp_u,
                "dominio": "-",
                "host": "",
                "base_key": "",
                "tipo": "",
                "bit": "",
                "resultado": "sin_servidor",
                "mensaje": "sin servidores SCADA configurados",
                "accion": action_label,
            })
            return updates, True

        # Seleccionar CC online y QADS (QA) una sola vez por empresa
        selected_hosts: list[tuple[str, str]] = []

        def _pick_online(domain_label: str) -> Optional[tuple[str, str]]:
            for dom, host in hosts:
                if dom != domain_label:
                    continue
                label = f"{emp_u} {dom}"
                client = None
                try:
                    client = sshserver(host, logger, logger_console)
                    if client is None:
                        raise RuntimeError("sshserver returned None")
                    host_online = None
                    if scada_online is not None:
                        try:
                            host_online = scada_online(client, logger, logger_console)
                        except Exception as exc:
                            msg = f"[SCADA] {label}: error verificando estado ONLINE ({exc})"
                            updates.append(msg)
                            has_fail = True
                            scada_actions.append({
                                "empresa": emp_u,
                                "dominio": dom,
                                "host": host,
                                "base_key": "",
                                "tipo": "",
                                "bit": "",
                                "resultado": "error_estado",
                                "mensaje": str(exc),
                                "accion": action_label,
                            })
                    if scada_online is not None and not host_online:
                        msg = f"[SCADA] {label}: sin estado ONLINE; se omiten updates."
                        updates.append(msg)
                        has_fail = True
                        scada_actions.append({
                            "empresa": emp_u,
                            "dominio": dom,
                            "host": host,
                            "base_key": "",
                            "tipo": "",
                            "bit": "",
                            "resultado": "offline",
                            "mensaje": "host sin estado ONLINE",
                            "accion": action_label,
                        })
                        continue
                    return label, host
                except Exception as exc:
                    msg = f"[SCADA] {label}: error conectando ({exc})"
                    updates.append(msg)
                    has_fail = True
                    scada_actions.append({
                        "empresa": emp_u,
                        "dominio": dom,
                        "host": host,
                        "base_key": "",
                        "tipo": "",
                        "bit": "",
                        "resultado": "error_conexion",
                        "mensaje": str(exc),
                        "accion": action_label,
                    })
                finally:
                    if client is not None:
                        try:
                            client.close()
                        except Exception:
                            pass
            return None

        # CC
        cc = _pick_online("CC")
        if cc:
            selected_hosts.append(cc)
        else:
            msg = f"[SCADA] {emp_u}: no se encontro SCADA CC ONLINE para {accion.lower()}."
            updates.append(msg)
            has_fail = True

        # QA / QADS
        qa = _pick_online("QA")
        if qa:
            selected_hosts.append(qa)

        if not selected_hosts:
            return updates, has_fail

        # Aplicar dbset en hosts seleccionados (CC online y QADS)
        try:
            for domain_label, host in selected_hosts:
                label = f"{emp_u} {domain_label}"
                client = None
                try:
                    client = sshserver(host, logger, logger_console)
                    if client is None:
                        raise RuntimeError("sshserver returned None")
                    for base, suffixes in base_suffix_map.items():
                        base_u = base.strip().upper()
                        if not base_u:
                            continue
                        suffix_union = {s.strip().upper() for s in suffixes if s}
                        suffix_union.update(scada_suffixes.get(base_u, set()))
                        scada_entry = info_emp.get(base_u)
                        tipo, bit = _determine_scada_action(list(suffix_union), scada_entry) if suffix_union else _determine_scada_action([], scada_entry)
                        valor = 1 if enable else 0
                        cmd = f". ~/.bash_profile && dbset -k 10 {tipo} 12 {base_u} {bit} = {valor}"
                        stdin, stdout, stderr = client.exec_command(cmd)
                        rc = stdout.channel.recv_exit_status()
                        if rc == 0:
                            msg = f"[SCADA] {label}: {accion} OK {base_u} bit {bit}"
                            updates.append(msg)
                            scada_actions.append({
                                "empresa": emp_u,
                                "dominio": domain_label,
                                "host": host,
                                "base_key": base_u,
                                "tipo": str(tipo),
                                "bit": str(bit),
                                "resultado": "ok",
                                "mensaje": f"{accion.lower()} ok",
                                "accion": action_label,
                            })
                        else:
                            err = stderr.read().decode("utf-8", "ignore").strip()
                            msg = f"[SCADA] {label}: fallo {accion.lower()} {base_u} bit {bit} ({err or f'rc={rc}'})"
                            updates.append(msg)
                            has_fail = True
                            scada_actions.append({
                                "empresa": emp_u,
                                "dominio": domain_label,
                                "host": host,
                                "base_key": base_u,
                                "tipo": str(tipo),
                                "bit": str(bit),
                                "resultado": "error",
                                "mensaje": err or f"rc={rc}",
                                "accion": action_label,
                            })
                except Exception as exc:
                    msg = f"[SCADA] {label}: error conectando o ejecutando comandos ({exc})"
                    updates.append(msg)
                    has_fail = True
                    scada_actions.append({
                        "empresa": emp_u,
                        "dominio": domain_label,
                        "host": host,
                        "base_key": "",
                        "tipo": "",
                        "bit": "",
                        "resultado": "error_conexion",
                        "mensaje": str(exc),
                        "accion": action_label,
                    })
                finally:
                    if client is not None:
                        try:
                            client.close()
                        except Exception:
                            pass
        finally:
            for key, value in prev_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        return updates, has_fail

    total_candidates: int = 0
    ready_candidates: int = 0

    def _on_progress_eliminar(line: str):
        nonlocal total_candidates, ready_candidates
        line = (line or "").strip()
        if not line:
            return

        lower = line.lower()
        tag = "info"
        if "error" in lower:
            tag = "error"
        elif "warn" in lower:
            tag = "warn"

        if line.startswith("REPORT_PATH:"):
            report_paths.append(line.split(":", 1)[1].strip())
        elif line.startswith("DELETE_FILE:"):
            delete_files.append(line.split(":", 1)[1].strip())
        elif line.startswith("PURGE_FILE:"):
            purge_files.append(line.split(":", 1)[1].strip())
        elif line.startswith("LOOKUP_STATUS:"):
            try:
                _, payload = line.split("LOOKUP_STATUS:", 1)
                emp, base, status = payload.split(":", 2)
                emp_u = emp.strip().upper()
                lookup_statuses[emp_u][base.strip()] = status.strip().upper()
            except Exception:
                pass
        elif line.startswith("GROUP_MATCH:"):
            try:
                _, payload = line.split("GROUP_MATCH:", 1)
                emp, base, raw = payload.split(":", 2)
                emp_u = emp.strip().upper()
                try:
                    details = json.loads(raw) if raw else []
                except json.JSONDecodeError:
                    details = []
                if isinstance(details, list):
                    group_matches[emp_u][base.strip()] = details
            except Exception:
                pass
        elif line.startswith("LOOKUP_DELETE:"):
            try:
                _, payload = line.split("LOOKUP_DELETE:", 1)
                emp, val = payload.split(":", 1)
                lookup_deleted[emp.strip().upper()] = int(val.strip() or 0)
            except Exception:
                pass
        elif line.startswith("LOOKUP_REMAINING:"):
            try:
                _, payload = line.split("LOOKUP_REMAINING:", 1)
                emp, val = payload.split(":", 1)
                lookup_remaining[emp.strip().upper()] = int(val.strip() or 0)
            except Exception:
                pass
        elif line.startswith("LOOKUP_WOULD_DELETE:"):
            try:
                _, payload = line.split("LOOKUP_WOULD_DELETE:", 1)
                emp, keys_part = payload.split(":", 1)
                emp_u = emp.strip().upper()
                keys = [k.strip() for k in keys_part.split(",") if k.strip()]
                lookup_would_delete[emp_u] = keys
                ready_candidates += len(keys)
            except Exception:
                pass
        elif line.startswith("LOOKUP_REMOVED:"):
            try:
                _, payload = line.split("LOOKUP_REMOVED:", 1)
                emp, keys_part = payload.split(":", 1)
                emp_u = emp.strip().upper()
                keys = [k.strip() for k in keys_part.split(",") if k.strip()]
                lookup_removed[emp_u] = keys
            except Exception:
                pass
        elif line.startswith("LOOKUP_STILL:"):
            try:
                _, payload = line.split("LOOKUP_STILL:", 1)
                emp, keys_part = payload.split(":", 1)
                emp_u = emp.strip().upper()
                keys = [k.strip() for k in keys_part.split(",") if k.strip()]
                lookup_still[emp_u] = keys
                if keys:
                    tag = "warn"
            except Exception:
                pass
        elif line.startswith("DELETE_KEYS:"):
            try:
                _, payload = line.split("DELETE_KEYS:", 1)
                emp, keys_part = payload.split(":", 1)
                emp_u = emp.strip().upper()
                keys = [k.strip() for k in keys_part.split(",") if k.strip()]
                delete_keys_by_emp[emp_u].update(keys)
            except Exception:
                pass

        _console(f"[ELIMINAR] {line}", tag)

    def _lookup_table_paths(emp: str) -> list[Path]:
        emp_u = (emp or "").upper()
        return list({
            Path(cwd) / "out" / emp_u / "HSH" / "lookup_table.csv",
            Path(app.base_dir) / "out" / emp_u / "HSH" / "lookup_table.csv",
        })

    def _collect_lookup_entries(emp: str) -> Set[str]:
        entries: Set[str] = set()
        for path in _lookup_table_paths(emp):
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
                    for row in csv.DictReader(fh):
                        val = (row.get("key") or row.get("Key") or "").strip()
                        if val:
                            entries.add(val)
            except Exception as exc:
                _console(f"[VERIFICAR:{emp}] No se pudo leer {path}: {exc}", "warn")
        return entries

    def _log_verify_output(emp: str, line: str) -> None:
        line = (line or "").strip()
        if not line:
            return
        _console(f"[VERIFICAR:{emp}] {line}", "info")

    # ---------- Apagado SCADA (siempre) ----------
    def _apagar_bits_scada():
        updates: list[str] = []
        if not delete_keys_by_emp:
            _console("[SCADA] No hay claves registradas para apagar en SCADA.", "info")
            return updates

        _console("[SCADA] Ejecutando apagado de bits en todos los SCADA configurados...", "warn")
        has_fail_global = False
        for emp_u, keys in delete_keys_by_emp.items():
            if not keys:
                continue
            base_map: dict[str, set[str]] = {}
            for raw_key in sorted(keys):
                key = (raw_key or "").strip()
                if not key:
                    continue
                base, dot, suf = key.partition(".")
                base_u = base.strip().upper()
                if not base_u:
                    continue
                suffixes = base_map.setdefault(base_u, set())
                if dot and suf:
                    suffixes.add(suf.strip().upper())
            updates_emp, fail_emp = _apply_scada_dbset(emp_u, base_map, enable=False, action_label="apagado-final")
            for line in updates_emp:
                lower = line.lower()
                if any(token in lower for token in ("error", "fallo", "offline", "omit", "warn", "sin estado")):
                    tag = "error" if "error" in lower or "fallo" in lower else "warn"
                else:
                    tag = "info"
                _console(f"[SCADA] {line}", tag)
                updates.append(line)
            if fail_emp:
                has_fail_global = True

        if has_fail_global:
            _console("[SCADA] Hubo incidencias al apagar bits; revisa los detalles previos.", "error")
        else:
            _console("[SCADA] Apagado de bits finalizado sin errores.", "info")

        return updates
    # ---------- Ejecuci??n de scripts (2 llamadas independientes) ----------
    def _run_eliminar_scripts():
        queue = list(run_targets)

        def _after_process(rc: int, emp: str) -> None:
            if rc != 0:
                _fail(f"El proceso para {emp} termin?? con errores")
                return
            _run_next()

        def _run_next():
            if not queue:
                if aplicar:
                    _console("[VERIFICAR] Scripts completados. Iniciando verificaci??n de lookup_table...", "info")
                    _start_verification()
                else:
                    _finish(0)
                return

            target_emp, target_respaldo, target_server = queue.pop(0)
            if not target_emp or not target_server:
                _run_next()
                return

            cmd = build_cmd("scripts.hsh_eliminar_tag", target_emp, "--input", excel_path)
            if target_respaldo:
                cmd += ["--respaldo", target_respaldo]
            if aplicar:
                cmd += ["--apply", "--server", target_server]
                respaldo_server = server_map.get(target_respaldo) if target_respaldo else None
                if respaldo_server:
                    cmd += ["--server-respaldo", respaldo_server]

            _console(f">> CMD[ELIMINAR:{target_emp}]: {' '.join(map(str, cmd))}", "warn")
            app.tasks.run_subprocess(
                cmd,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_eliminar,
                on_done=lambda rc, e=target_emp: _after_process(rc, e),
            )

        _run_next()

    def _post_verification_success():
        if aplicar:
            _console("[SCADA] Apagando bits en todos los servidores...", "warn")
            _apagar_bits_scada()
            _finish(0)
        else:
            msg_resumen = f"Tags listos para eliminar: {ready_candidates}"
            _finish(0, msg_resumen)

    def _start_verification():
        verify_queue: list[tuple[str, str, list[str]]] = []
        for emp_name, server_name in server_map.items():
            if not emp_name or not server_name:
                continue
            keys = sorted({k for k in lookup_removed.get(emp_name, []) if k})
            if not keys and lookup_still.get(emp_name):
                keys = sorted({k for k in lookup_still.get(emp_name, []) if k})
            if keys:
                verify_queue.append((emp_name, server_name, keys))

        if not verify_queue:
            _console("[VERIFICAR] No hay claves para confirmar en lookup_table; se continuara con el apagado de bits.", "info")
            _post_verification_success()
            return

        _console("[VERIFICAR] Reimportando dumps HSH para confirmar eliminaciones.", "info")

        def _run_verify_next():
            if not verify_queue:
                _post_verification_success()
                return
            emp_name, server_name, keys = verify_queue.pop(0)
            _console(f"[VERIFICAR:{emp_name}] Importando HSH...", "info")
            import_cmd = build_cmd("scripts.importar_all", server_name, emp_name, "hsh", "--usecase", "hsh_eliminar_tag")
            app.tasks.run_subprocess(
                import_cmd,
                env=env,
                cwd=cwd,
                on_progress=lambda line, e=emp_name: _log_verify_output(e, line),
                on_done=lambda rc, e=emp_name, s=server_name, ks=keys: _after_import(rc, e, s, ks),
            )

        def _after_import(rc: int, emp_name: str, server_name: str, keys: list[str]) -> None:
            if rc != 0:
                verify_queue.clear()
                verification_failures[emp_name] = keys
                _fail(f"Import HSH para {emp_name} fall?? (rc={rc}) durante verificaci??n.")
                return
            _console(f"[VERIFICAR:{emp_name}] Import HSH OK, convirtiendo...", "info")
            convert_cmd = build_cmd("scripts.Convertir_all", emp_name, "Validar_HSH", "--only", "hsh")
            app.tasks.run_subprocess(
                convert_cmd,
                env=env,
                cwd=cwd,
                on_progress=lambda line, e=emp_name: _log_verify_output(e, line),
                on_done=lambda rc, e=emp_name, ks=keys: _after_convert(rc, e, ks),
            )

        def _after_convert(rc: int, emp_name: str, keys: list[str]) -> None:
            if rc != 0:
                verify_queue.clear()
                verification_failures[emp_name] = keys
                _fail(f"Conversi??n HSH para {emp_name} fall?? (rc={rc}) durante verificaci??n.")
                return
            existing = _collect_lookup_entries(emp_name)
            still_present = [k for k in keys if k in existing]
            if still_present:
                verify_queue.clear()
                verification_failures[emp_name] = still_present
                joined = ", ".join(still_present)
                _console(f"[VERIFICAR:{emp_name}] Claves persistentes en lookup_table: {joined}", "error")
                _fail(f"Verificaci??n HSH fallida para {emp_name}: {len(still_present)} claves siguen presentes en lookup_table.")
                return
            verified_removed[emp_name] = keys
            _console(f"[VERIFICAR:{emp_name}] lookup_table sin claves objetivo ({len(keys)} verificadas).", "info")
            _run_verify_next()

        _run_verify_next()
    # ---------- Finalización ----------
    def _restore_buttons():
        for b in botones:
            try:
                default_text = " Eliminar " if b is getattr(app, "boton_eliminar_tag_hsh", None) else " Validar "
                b.config(text=default_text, state="normal")
            except Exception:
                pass

    def _finish(rc: int, msg: str | None = None):
        def _end():
            _restore_buttons()
            app.stop_status()

            summary_text, removed_list, pending_list = _build_eliminar_summary()
            detail_lines: List[str] = []

            # Modo validar: solo mostrar candidatos listos, sin hablar de eliminacion real
            if not aplicar and rc == 0:
                resumen = msg or "Tags listos para eliminar: 0"
                show_summary_dialog(
                    parent=app.ventana,
                    mensaje=resumen,
                    title="Validacion Eliminacion HSH lista",
                    status="success",
                    details=None,
                    files=report_paths or None,
                    show_open_file=bool(report_paths),
                )
                return

            attachments: List[str] = []
            dialog_status = "success" if rc == 0 else "error"
            dialog_title = "Eliminacion HSH completa" if rc == 0 else "Eliminacion HSH con errores"

            if rc == 0:
                resumen: list[str] = []

                def _format_group_list(emp_code: str, base_key: str) -> str:
                    entries = group_matches.get(emp_code, {}).get(base_key, [])
                    if not entries:
                        return "sin coincidencias en groups"
                    formatted: list[str] = []
                    for entry in entries:
                        cpid = (entry.get("cpid") or "").strip()
                        uid = (entry.get("uid") or "").strip()
                        point = (entry.get("point") or "").strip()
                        variant = (entry.get("variant") or "").strip()
                        label_parts: list[str] = []
                        if cpid or uid:
                            combo = "/".join(part for part in (cpid, uid) if part)
                            if combo:
                                label_parts.append(combo)
                        if point:
                            label_parts.append(point)
                        elif variant and variant != base_key:
                            label_parts.append(variant)
                        label = " ".join(label_parts).strip()
                        if not label:
                            label = variant or "sin detalle"
                        formatted.append(label)
                    if len(formatted) > 6:
                        extra = len(formatted) - 6
                        return ", ".join(formatted[:6]) + f", ... (+{extra})"
                    return ", ".join(formatted)

                report_excel_path: Optional[str] = None

                def _generate_report_excel() -> Optional[str]:
                    if not aplicar:
                        return None
                    if Workbook is None:
                        _console("[REPORT] openpyxl no disponible; no se genera reporte Excel.", "warn")
                        return None
                    try:
                        wb = Workbook()
                        summary_ws = wb.active
                        summary_ws.title = "Resumen"
                        summary_ws.append([
                            "Empresa",
                            "Claves entrada",
                            "Tags lookup eliminados",
                            "Tags lookup restantes",
                            "Claves verificacion OK",
                            "Claves con fallo",
                        ])
                        for emp in sorted(server_map.keys()):
                            input_bases = sorted({k.split(".", 1)[0] for k in delete_keys_by_emp.get(emp, set())})
                            verified_bases = sorted({k.split(".", 1)[0] for k in verified_removed.get(emp, [])})
                            fail_bases = sorted({k.split(".", 1)[0] for k in verification_failures.get(emp, [])})
                            summary_ws.append([
                                emp,
                                len(input_bases),
                                lookup_deleted.get(emp, 0),
                                lookup_remaining.get(emp, 0),
                                len(verified_bases),
                                len(fail_bases),
                            ])

                        detail_ws = wb.create_sheet("Detalle claves")
                        detail_ws.append([
                            "Empresa",
                            "BaseKey",
                            "Lookup status",
                            "Tags entrada",
                            "Tags lookup",
                            "Tags eliminados",
                            "Tags restantes",
                        ])
                        for emp in sorted(server_map.keys()):
                            statuses = lookup_statuses.get(emp, {})
                            bases = sorted(set(statuses.keys()) | set(lookup_would_delete.get(emp, [])))
                            for base in bases:
                                status_txt = statuses.get(base, "SIN INFO")
                                detail_ws.append([
                                    emp,
                                    base,
                                    status_txt,
                                    ", ".join(sorted(delete_keys_by_emp.get(emp, set()))),
                                    ", ".join(sorted(lookup_removed.get(emp, []))),
                                    ", ".join(sorted(verified_removed.get(emp, []))),
                                    ", ".join(sorted(lookup_still.get(emp, []))),
                                ])

                        scada_ws = wb.create_sheet("SCADA")
                        scada_ws.append(["Empresa", "Dominio", "Accion", "Estado", "Mensaje"])
                        for action in scada_actions:
                            scada_ws.append([
                                action.get("empresa"),
                                action.get("dominio"),
                                action.get("accion"),
                                action.get("estado"),
                                action.get("mensaje"),
                            ])

                        if delete_files:
                            report_dir = Path(delete_files[0]).parent
                        else:
                            report_dir = Path(app.base_dir) / "out" / "eliminar_tag"
                        report_dir.mkdir(parents=True, exist_ok=True)
                        report_path = report_dir / f"reporte_eliminar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        wb.save(report_path)
                        _console(f"[REPORT] Reporte Excel generado en {report_path}", "info")
                        return str(report_path)
                    except Exception as exc:
                        _console(f"[REPORT] Error generando reporte Excel: {exc}", "error")
                        return None

                if not aplicar:
                    for emp in sorted(server_map.keys()):
                        resumen.append(f"{emp}:")
                        statuses = lookup_statuses.get(emp, {})
                        bases = sorted(set(statuses.keys()) | set(group_matches.get(emp, {}).keys()))
                        if bases:
                            for base in bases:
                                status_txt = statuses.get(base, "ABSENT").lower()
                                group_desc = _format_group_list(emp, base)
                                resumen.append(f"  {base}: lookup={status_txt}; groups={group_desc}")
                        else:
                            resumen.append("  Sin datos de lookup_table ni groups.")
                        keys_preview = lookup_would_delete.get(emp, [])
                        if keys_preview:
                            listado = ", ".join(keys_preview)
                            resumen.append(f"  Se eliminarian {len(keys_preview)} claves de lookup_table: {listado}")
                else:
                    for emp in sorted(server_map.keys()):
                        deleted = lookup_deleted.get(emp, 0)
                        rem = lookup_remaining.get(emp, 0)
                        resumen.append(f"{emp}: eliminados={deleted}, restantes={rem}")
                        removed_keys = lookup_removed.get(emp, [])
                        if removed_keys:
                            resumen.append(f"{emp}: claves eliminadas de lookup_table ({len(removed_keys)}): {', '.join(removed_keys)}")
                        still_keys = lookup_still.get(emp, [])
                        if still_keys:
                            resumen.append(f"{emp}: claves aun presentes en lookup_table ({len(still_keys)}): {', '.join(still_keys)}")
                        verified_keys = verified_removed.get(emp, [])
                        if verified_keys:
                            resumen.append(f"{emp}: verificacion lookup_table OK ({len(verified_keys)} claves).")
                        bases = sorted(set(lookup_statuses.get(emp, {}).keys()) | set(group_matches.get(emp, {}).keys()))
                        for base in bases:
                            status_txt = lookup_statuses.get(emp, {}).get(base, "").lower() or "desconocido"
                            group_desc = _format_group_list(emp, base)
                            resumen.append(f"  {base}: lookup={status_txt}; groups={group_desc}")

                    report_excel_path = _generate_report_excel()
                    if report_excel_path:
                        attachments.append(report_excel_path)

                for emp in sorted(server_map.keys()):
                    deleted = lookup_deleted.get(emp, 0)
                    rem = lookup_remaining.get(emp, 0)
                    detail_lines.append(f"{emp}: eliminados={deleted}, restantes={rem}")
                    removed_keys = lookup_removed.get(emp, [])
                    if removed_keys:
                        detail_lines.append(f"{emp}: claves eliminadas de lookup_table ({len(removed_keys)}): {', '.join(removed_keys)}")
                attachments.extend(report_paths)
                attachments.extend(delete_files)
                attachments.extend(purge_files)
                app.success_status("Eliminacion completada")
            else:
                app.error_status("El proceso termino con errores")
                if msg:
                    detail_lines.append(msg)
                attachments.extend(report_paths)
                attachments.extend(delete_files)
                attachments.extend(purge_files)

            attachments = [path for path in dict.fromkeys(attachments) if path]
            show_summary_dialog(
                parent=app.ventana,
                mensaje=summary_text or (msg or "Sin informacion"),
                title=dialog_title,
                status=dialog_status,
                details=detail_lines or None,
                files=attachments or None,
                show_open_file=bool(attachments),
            )
        app.ventana.after(0, _end)

    def _fail(msg: str):
        _console(f"[ELIMINAR] {msg}", "error")
        _finish(1, msg)

    def _run_pre_scada_then_scripts():
        if not aplicar:
            _run_eliminar_scripts()
            return
        if not excel_scada_maps:
            _run_eliminar_scripts()
            return
        _set_status("Apagando bits de las claves actuales en SCADA...")
        _console("Apagando bits en todos los SCADA antes de iniciar...", "warn")
        fallo_inicial = False
        for emp_key, base_map in excel_scada_maps.items():
            emp_u = emp_key.upper()
            updates_emp, fail_emp = _apply_scada_dbset(emp_u, base_map, enable=False, action_label="pre-apagado")
            for linea in updates_emp:
                lower = linea.lower()
                if any(token in lower for token in ("error", "fallo", "failed", "traceback")):
                    tag = "error"
                elif any(token in lower for token in ("offline", "omit", "warn", "sin estado")):
                    tag = "warn"
                else:
                    tag = "info"
                _console(f"[SCADA-INICIAL] {linea}", tag)
            if fail_emp:
                fallo_inicial = True
        if fallo_inicial:
            _fail("No fue posible apagar los bits en SCADA antes de eliminar.")
            return
        _run_eliminar_scripts()

    def _run_update_pipeline():
        def _progress_logger(tag: str):
            def _inner(line: str):
                line = (line or "").strip()
                if not line:
                    return
                lower = line.lower()
                if any(token in lower for token in ("error", "fallo", "failed", "traceback")):
                    log_tag = "error"
                elif "warn" in lower or "warning" in lower:
                    log_tag = "warn"
                else:
                    log_tag = "info"
                _console(f"[{tag}] {line}", log_tag)
            return _inner

        def _run_conversion_sequence(emp_name: str, components: List[str], on_done):
            iterator = iter(components)

            def _run_next_component():
                try:
                    component = next(iterator)
                except StopIteration:
                    completed.append(emp_name)
                    on_done()
                    return

                _set_status(f"Convirtiendo {component.upper()} para {emp_name}...")
                cmd_conv = build_cmd("scripts.Convertir_all", emp_name, "Validar_HSH", "--only", component)
                _console(f">> CMD[CONVERT {emp_name}:{component}]: {' '.join(map(str, cmd_conv))}", "warn")

                app.tasks.run_subprocess(
                    cmd_conv,
                    env=env,
                    cwd=cwd,
                    on_progress=_progress_logger(f"CONVERT-{emp_name}-{component.upper()}"),
                    on_done=lambda rc: (_run_next_component() if rc == 0 else _fail(f"Conversion {component.upper()} para {emp_name} falló (rc={rc})")),
                )

            _run_next_component()

        def _run_import_sequence(emp_name: str, server_hint: Optional[str], on_success) -> None:
            host = (server_hint or "").strip()
            if not host:
                errors.append(f"{emp_name}: no se pudo resolver servidor SCADA principal para importar datos.")
                _fail(f"Importación SCADA/HSH para {emp_name} no tiene servidor principal disponible.")
                return

            _set_status(f"Importando datos para {emp_name} (perfil hsh_eliminar_tag)...")
            cmd_import = build_cmd(
                "scripts.importar_all",
                host,
                emp_name,
                "sca,hsh",
                "--usecase",
                "hsh_eliminar_tag",
            )
            _console(f">> CMD[IMPORT {emp_name}:{host}]: {' '.join(map(str, cmd_import))}", "warn")

            def _after_import(rc: int):
                if rc != 0:
                    errors.append(f"{emp_name}: importar_all terminó con rc={rc} (host {host})")
                    _fail(f"Importación SCADA/HSH para {emp_name} falló (rc={rc}).")
                    return
                _run_conversion_sequence(emp_name, ["sca", "hsh"], on_success)

            app.tasks.run_subprocess(
                cmd_import,
                env=env,
                cwd=cwd,
                on_progress=_progress_logger(f"IMPORT-{emp_name}@{host}"),
                on_done=_after_import,
            )

        def _after_principal():
            if not (respaldo and servidor_respaldo):
                _run_pre_scada_then_scripts()
                return
            _run_import_sequence(respaldo, servidor_respaldo, _run_pre_scada_then_scripts)

        _set_status("Sincronizando hsh_eliminar_tag (SCADA+HSH)...")
        _run_import_sequence(empresa, servidor_principal, _after_principal)

    # ---------- Inicio ----------
    if aplicar:
        _run_update_pipeline()
    else:
        _run_eliminar_scripts()

__all__ = ["ejecutar_eliminar_tag_hsh"]

