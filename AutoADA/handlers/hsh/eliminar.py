from __future__ import annotations

import csv
import json
import os
import pandas as pd
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from .common import (
    Logger,
    Workbook,
    build_cmd,
    messagebox,
    show_success_with_open,
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

    def _build_scada_descriptors(emp: str, base_suffix_map: dict[str, set[str]]) -> list[str]:
        emp_u = emp.upper()
        if not base_suffix_map:
            return []
        info_emp, scada_suffixes = _get_scada_metadata(emp_u)
        descriptors: list[str] = []
        for base, suffixes in base_suffix_map.items():
            base_u = base.upper()
            suffix_union = {s.strip().upper() for s in suffixes if s}
            suffix_union.update(scada_suffixes.get(base_u, set()))
            scada_entry = info_emp.get(base_u)
            tipo, bit = _determine_scada_action(suffix_union, scada_entry)
            hosts = [h for h in SCADA_HOSTS_FULL.get(emp_u, []) if h]
            if not hosts:
                fallback: list[str] = []
                for dom in ("CC", "QA"):
                    host = app.generar_server(emp_u, dom)
                    if host:
                        fallback.append(host)
                hosts = fallback
            if not hosts:
                _console(f"[SCADA] {emp_u}: no se encontraron hosts configurados para {base_u}", "warn")
                continue
            for host in hosts:
                domain = "QA" if "qds" in host.lower() else "CC"
                descriptors.append(f"{emp_u}|{domain}|{base_u}|{tipo}:{bit}")
        return list(dict.fromkeys(descriptors))

    def _execute_scada_actions(descriptors: list[str], enable: bool, record_storage: Optional[list[dict[str, str]]] = None) -> tuple[list[str], bool]:
        if not descriptors:
            return [], False
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
        updates: list[str] = []
        has_fail = False
        processed: set[tuple[str, str, str, int, int, bool]] = set()
        try:
            for descriptor in descriptors:
                parts = [p.strip() for p in descriptor.split("|")]
                if len(parts) < 4:
                    msg = f"Descriptor SCADA invalido: {descriptor}"
                    updates.append(msg)
                    has_fail = True
                    continue
                emp_key, domain, base_key, bit_spec = parts[:4]
                emp_u = emp_key.upper()
                try:
                    tipo_str, bit_str = bit_spec.split(":")
                    tipo = int(tipo_str)
                    bit = int(bit_str)
                except ValueError:
                    msg = f"Bit spec invalido: {bit_spec}"
                    updates.append(msg)
                    has_fail = True
                    continue
                candidates = [h for h in SCADA_HOSTS_FULL.get(emp_u, []) if h and ((domain.upper() == "QA" and "qds" in h.lower()) or (domain.upper() != "QA" and "qds" not in h.lower()))]
                if not candidates:
                    host = app.generar_server(emp_u, domain.upper())
                    if host:
                        candidates = [host]
                if not candidates:
                    msg = f"{emp_u} {domain}: sin host SCADA configurado"
                    updates.append(msg)
                    has_fail = True
                    continue
                for host in candidates:
                    key = (emp_u, host, base_key.upper(), tipo, bit, enable)
                    if key in processed:
                        continue
                    processed.add(key)
                    client = None
                    accion = "Encender" if enable else "Apagar"
                    try:
                        client = sshserver(host, logger, logger_console) if logger is not None else sshserver(host)
                        if client is None:
                            raise RuntimeError("sshserver retorno None")
                        host_online = None
                        if scada_online is not None:
                            host_online = scada_online(client, logger, logger_console)
                        if scada_online is not None and not host_online:
                            msg = f"SCADA {host}: sin estado ONLINE, se omite {accion.lower()} {base_key}"
                            updates.append(msg)
                            has_fail = True
                            if record_storage is not None:
                                record_storage.append({
                                    "empresa": emp_u,
                                    "dominio": "QA" if "qds" in host.lower() else "CC",
                                    "host": host,
                                    "base_key": base_key.upper(),
                                    "tipo": str(tipo),
                                    "bit": str(bit),
                                    "resultado": "offline",
                                    "mensaje": msg,
                                })
                            continue
                        valor = 1 if enable else 0
                        cmd = f". ~/.bash_profile && dbset -k 10 {tipo} 12 {base_key} {bit} = {valor}"
                        stdin, stdout, stderr = client.exec_command(cmd)
                        rc = stdout.channel.recv_exit_status()
                        if rc == 0:
                            msg = f"SCADA {host}: {accion} OK {base_key} bit {bit}"
                            updates.append(msg)
                            if record_storage is not None:
                                record_storage.append({
                                    "empresa": emp_u,
                                    "dominio": "QA" if "qds" in host.lower() else "CC",
                                    "host": host,
                                    "base_key": base_key.upper(),
                                    "tipo": str(tipo),
                                    "bit": str(bit),
                                    "resultado": "ok",
                                    "mensaje": msg,
                                })
                        else:
                            err = stderr.read().decode("utf-8", "ignore").strip()
                            msg = f"SCADA {host}: fallo {base_key} bit {bit} (rc={rc}) {err}"
                            updates.append(msg)
                            has_fail = True
                            if record_storage is not None:
                                record_storage.append({
                                    "empresa": emp_u,
                                    "dominio": "QA" if "qds" in host.lower() else "CC",
                                    "host": host,
                                    "base_key": base_key.upper(),
                                    "tipo": str(tipo),
                                    "bit": str(bit),
                                    "resultado": "error",
                                    "mensaje": msg,
                                })
                    except Exception as exc:
                        msg = f"SCADA {host}: error {base_key} bit {bit}: {exc}"
                        updates.append(msg)
                        has_fail = True
                        if record_storage is not None:
                            record_storage.append({
                                "empresa": emp_u,
                                "dominio": "QA" if "qds" in host.lower() else "CC",
                                "host": host,
                                "base_key": base_key.upper(),
                                "tipo": str(tipo),
                                "bit": str(bit),
                                "resultado": "error",
                                "mensaje": msg,
                            })
                    finally:
                        if client is not None:
                            try:
                                client.close()
                            except Exception:
                                pass
        finally:
            for k, v in prev_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return updates, has_fail

    # ---------- Parser de salida del script ----------
    def _on_progress_eliminar(line: str):
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

        descriptors: list[str] = []
        for emp_u, keys in delete_keys_by_emp.items():
            if not keys:
                continue
            base_suffix_map: dict[str, set[str]] = {}
            for raw_key in sorted(keys):
                key = (raw_key or "").strip()
                if not key:
                    continue
                base, dot, suf = key.partition(".")
                base_u = base.strip().upper()
                if not base_u:
                    continue
                suffixes = base_suffix_map.setdefault(base_u, set())
                if dot and suf:
                    suffixes.add(suf.strip().upper())
            descriptors.extend(_build_scada_descriptors(emp_u, base_suffix_map))

        if not descriptors and excel_scada_maps:
            for emp_u, base_map in excel_scada_maps.items():
                descriptors.extend(_build_scada_descriptors(emp_u, base_map))

        descriptors = list(dict.fromkeys(descriptors))
        if not descriptors:
            _console("[SCADA] No se generaron descriptores para apagar bits.", "warn")
            return updates

        _console("[SCADA] Ejecutando apagado de bits en todos los SCADA configurados...", "warn")
        actions_updates, has_fail = _execute_scada_actions(descriptors, enable=False, record_storage=scada_actions)
        for line in actions_updates:
            lower = line.lower()
            if any(token in lower for token in ("error", "fallo", "offline", "omit")):
                tag = "error" if "error" in lower or "fallo" in lower else "warn"
            else:
                tag = "info"
            _console(f"[SCADA] {line}", tag)
            updates.append(line)

        if has_fail:
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
        _console("[SCADA] Apagando bits en todos los servidores...", "warn")
        _apagar_bits_scada()
        _finish(0)

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
            _console("[VERIFICAR] No hay claves para confirmar en lookup_table; se continuar?? con el apagado de bits.", "info")
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

                    def _fmt_list(values: list[str]) -> str:
                        if not values:
                            return "-"
                        return f"{len(values)} -> " + ", ".join(values)

                    try:
                        wb = Workbook()
                        summary_ws = wb.active
                        summary_ws.title = "Resumen"
                        summary_ws.append([
                            "Empresa",
                            "Claves entrada",
                            "Tags lookup eliminados",
                            "Tags lookup restantes",
                            "Claves verificación OK",
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
                            "Verificación",
                            "Groups",
                            "SCADA acciones",
                        ])

                        for emp in sorted(server_map.keys()):
                            base_union: Set[str] = set()
                            base_union.update(k.split(".", 1)[0] for k in delete_keys_by_emp.get(emp, set()))
                            base_union.update(lookup_statuses.get(emp, {}).keys())
                            base_union.update(group_matches.get(emp, {}).keys())
                            base_union.update(k.split(".", 1)[0] for k in lookup_would_delete.get(emp, []))
                            base_union.update(k.split(".", 1)[0] for k in lookup_removed.get(emp, []))
                            base_union.update(k.split(".", 1)[0] for k in lookup_still.get(emp, []))
                            base_union.update(k.split(".", 1)[0] for k in verified_removed.get(emp, []))
                            base_union.update(k.split(".", 1)[0] for k in verification_failures.get(emp, []))

                            for base in sorted(base_union):
                                input_variants = sorted(k for k in delete_keys_by_emp.get(emp, set()) if k.startswith(base))
                                would_list = sorted(k for k in lookup_would_delete.get(emp, []) if k.startswith(base))
                                removed_list = sorted(k for k in lookup_removed.get(emp, []) if k.startswith(base))
                                still_list = sorted(k for k in lookup_still.get(emp, []) if k.startswith(base))
                                verified_list = sorted(k for k in verified_removed.get(emp, []) if k.startswith(base))
                                fail_keys = sorted(k for k in verification_failures.get(emp, []) if k.startswith(base))
                                lookup_union = sorted(set(input_variants) | set(would_list) | set(removed_list) | set(still_list))
                                status_lookup = (lookup_statuses.get(emp, {}).get(base, "") or "").lower() or "desconocido"
                                group_entries = group_matches.get(emp, {}).get(base, [])
                                group_texts: list[str] = []
                                for entry in group_entries:
                                    variant = (entry.get("variant") or base).strip()
                                    cpid = (entry.get("cpid") or "").strip()
                                    uid = (entry.get("uid") or "").strip()
                                    point = (entry.get("point") or "").strip()
                                    pieces: list[str] = []
                                    if variant:
                                        pieces.append(variant)
                                    path = "/".join(part for part in (cpid, uid) if part)
                                    if path:
                                        pieces.append(path)
                                    if point:
                                        pieces.append(point)
                                    group_texts.append(" | ".join(pieces))

                                scada_texts: list[str] = []
                                for action in scada_actions:
                                    if action.get("empresa") != emp:
                                        continue
                                    base_key = action.get("base_key")
                                    if base_key and base_key.split(".", 1)[0] == base:
                                        dom = action.get("dominio") or "-"
                                        host = action.get("host") or "-"
                                        bit = action.get("bit") or "-"
                                        resultado = action.get("resultado") or "-"
                                        mensaje = action.get("mensaje") or "-"
                                        scada_texts.append(f"{dom}/{host} bit {bit} -> {resultado} ({mensaje})")

                                if not scada_texts:
                                    generic_actions = [
                                        action for action in scada_actions
                                        if action.get("empresa") == emp and not action.get("base_key")
                                    ]
                                    for action in generic_actions:
                                        dom = action.get("dominio") or "-"
                                        host = action.get("host") or "-"
                                        resultado = action.get("resultado") or "-"
                                        mensaje = action.get("mensaje") or "-"
                                        scada_texts.append(f"{dom}/{host} -> {resultado} ({mensaje})")

                                if fail_keys:
                                    status_text = f"FALLO ({', '.join(fail_keys)})"
                                elif verified_list:
                                    status_text = f"OK ({len(verified_list)} claves)"
                                elif lookup_union:
                                    status_text = "Procesado"
                                else:
                                    status_text = "Sin actividad"

                                detail_ws.append([
                                    emp,
                                    base,
                                    status_lookup,
                                    _fmt_list(input_variants),
                                    _fmt_list(lookup_union),
                                    _fmt_list(removed_list),
                                    _fmt_list(still_list),
                                    status_text,
                                    _fmt_list(group_texts),
                                    _fmt_list(scada_texts),
                                ])

                        if scada_actions:
                            scada_ws = wb.create_sheet("SCADA")
                            scada_ws.append(["Empresa", "Dominio", "Host", "BaseKey", "Tipo", "Bit", "Resultado", "Mensaje"])
                            for action in scada_actions:
                                scada_ws.append([
                                    action.get("empresa"),
                                    action.get("dominio"),
                                    action.get("host"),
                                    action.get("base_key"),
                                    action.get("tipo"),
                                    action.get("bit"),
                                    action.get("resultado"),
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

                message = "\n".join(resumen) or "Eliminacion completada correctamente."
                files_to_show: list[str] = [*report_paths, *delete_files, *purge_files]
                if report_excel_path:
                    files_to_show.append(report_excel_path)
                show_success_with_open(
                    parent=app.ventana,
                    mensaje=message,
                    title="Eliminación HSH completa",
                    files=files_to_show,
                )
                app.success_status("Eliminación completada")
            else:
                app.error_status("El proceso terminó con errores")
                messagebox.showerror("Error", msg or "El proceso terminó con errores.", parent=app.ventana)
        app.ventana.after(0, _end)

    def _fail(msg: str):
        _console(f"[ELIMINAR] {msg}", "error")
        _finish(1, msg)

    def _run_pre_scada_then_scripts():
        if not aplicar:
            _run_eliminar_scripts()
            return
        descriptors: list[str] = []
        if excel_scada_maps:
            for emp_key, base_map in excel_scada_maps.items():
                descriptors.extend(_build_scada_descriptors(emp_key, base_map))
        descriptors = list(dict.fromkeys(descriptors))
        if not descriptors:
            _run_eliminar_scripts()
            return
        _set_status("Apagando bits de las claves actuales en SCADA...")
        _console("Apagando bits en todos los SCADA antes de iniciar...", "warn")
        resumen_inicial, fallo_inicial = _execute_scada_actions(
            descriptors,
            enable=False,
            record_storage=scada_actions,
        )
        for linea in resumen_inicial:
            lower = linea.lower()
            if any(token in lower for token in ("error", "fallo", "failed", "traceback")):
                tag = "error"
            elif any(token in lower for token in ("offline", "omit", "warn")):
                tag = "warn"
            else:
                tag = "info"
            _console(f"[SCADA-INICIAL] {linea}", tag)
        if fallo_inicial:
            _fail("No fue posible apagar los bits en SCADA antes de eliminar.")
            return
        _run_eliminar_scripts()

    def _run_update_pipeline():
        cmd_import_principal = build_cmd(
            "scripts.importar_all",
            servidor_principal,
            empresa,
            "sca,hsh",
            "--usecase",
            "hsh_eliminar_tag",
        )
        cmd_import_respaldo = (
            build_cmd(
                "scripts.importar_all",
                servidor_respaldo,
                respaldo,
                "sca,hsh",
                "--usecase",
                "hsh_eliminar_tag",
            )
            if respaldo and servidor_respaldo
            else None
        )
        cmd_conv_sca = build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "sca")
        cmd_conv_hsh = build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "hsh")
        cmd_conv_sca_res = (
            build_cmd("scripts.Convertir_all", respaldo, "Validar_HSH", "--only", "sca")
            if respaldo
            else None
        )
        cmd_conv_hsh_res = (
            build_cmd("scripts.Convertir_all", respaldo, "Validar_HSH", "--only", "hsh")
            if respaldo
            else None
        )

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

        def _run_convert_hsh_res():
            if not (respaldo and cmd_conv_hsh_res):
                _run_pre_scada_then_scripts()
                return
            _set_status(f"Convirtiendo HSH respaldo {respaldo}...")
            _console(f">> CMD[CONVERT HSH respaldo]: {' '.join(map(str, cmd_conv_hsh_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_hsh_res,
                env=env,
                cwd=cwd,
                on_progress=_progress_logger("CONVERT-HSH-RES"),
                on_done=lambda rc: (_run_pre_scada_then_scripts() if rc == 0 else _fail(f"Conversion HSH respaldo ({respaldo}) fallo")),
            )

        def _run_convert_sca_res():
            if not (respaldo and cmd_conv_sca_res):
                _run_convert_hsh_res()
                return
            _set_status(f"Convirtiendo SCADA respaldo {respaldo}...")
            _console(f">> CMD[CONVERT SCADA respaldo]: {' '.join(map(str, cmd_conv_sca_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_sca_res,
                env=env,
                cwd=cwd,
                on_progress=_progress_logger("CONVERT-SCADA-RES"),
                on_done=lambda rc: (_run_convert_hsh_res() if rc == 0 else _fail(f"Conversion SCADA respaldo ({respaldo}) fallo")),
            )

        def _run_convert_hsh():
            _set_status("Convirtiendo HSH principal...")
            _console(f">> CMD[CONVERT HSH principal]: {' '.join(map(str, cmd_conv_hsh))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_hsh,
                env=env,
                cwd=cwd,
                on_progress=_progress_logger("CONVERT-HSH"),
                on_done=lambda rc: (_run_convert_sca_res() if rc == 0 else _fail("Conversion HSH principal fallo")),
            )

        def _run_convert_sca():
            _set_status("Convirtiendo SCADA principal...")
            _console(f">> CMD[CONVERT SCADA principal]: {' '.join(map(str, cmd_conv_sca))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_sca,
                env=env,
                cwd=cwd,
                on_progress=_progress_logger("CONVERT-SCADA"),
                on_done=lambda rc: (_run_convert_hsh() if rc == 0 else _fail("Conversion SCADA principal fallo")),
            )

        def _run_import_res():
            if not cmd_import_respaldo:
                _run_convert_sca()
                return
            _set_status(f"Sincronizando hsh_eliminar_tag respaldo ({respaldo})...")
            _console(f">> CMD[IMPORT respaldo]: {' '.join(map(str, cmd_import_respaldo))}", "warn")
            app.tasks.run_subprocess(
                cmd_import_respaldo,
                env=env,
                cwd=cwd,
                on_progress=_progress_logger("IMPORT-RES"),
                on_done=lambda rc: (_run_convert_sca() if rc == 0 else _fail("Importacion SCADA/HSH respaldo fallo")),
            )

        def _after_import_principal(rc: int):
            if rc != 0:
                _fail("Importacion SCADA/HSH principal fallo")
                return
            _run_import_res()

        _set_status("Sincronizando hsh_eliminar_tag (SCADA+HSH)...")
        _console(f">> CMD[IMPORT principal]: {' '.join(map(str, cmd_import_principal))}", "warn")
        app.tasks.run_subprocess(
            cmd_import_principal,
            env=env,
            cwd=cwd,
            on_progress=_progress_logger("IMPORT-PRI"),
            on_done=_after_import_principal,
        )

    # ---------- Inicio ----------
    if aplicar:
        _run_update_pipeline()
    else:
        _run_eliminar_scripts()

__all__ = ["ejecutar_eliminar_tag_hsh"]
