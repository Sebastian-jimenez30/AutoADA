from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .common import (
    Logger,
    build_cmd,
    company_prefixes,
    collect_pi_snapshots,
    load_workbook,
    messagebox,
    show_summary_dialog,
    sshserver,
    scada_online,
    SCADA_HOSTS_FULL,
    tk,
)
from utils.paths import output_root

def ejecutar_crear_tag_hsh(app, aplicar: bool = False, origin: str | None = None):
    """Valida un Excel y opcionalmente crea tags en HSH (con verificacion, PI y SCADA)."""

    ENABLE_PI_CHECKS = False

    # ---------- Inputs UI ----------
    empresa_var = getattr(app, "opcion_empresa_hsh_crear", None)
    if not empresa_var:
        messagebox.showerror("Error", "No se encontro configuracion para esta vista."); return
    empresa = (empresa_var.get() or "").strip()
    if not empresa or empresa == "Empresa...":
        messagebox.showerror("Error", "Selecciona una empresa."); return

    excel_path = getattr(app, "hsh_crear_tag_file", None)
    if not excel_path or not os.path.isfile(excel_path):
        messagebox.showerror("Error", "Selecciona el Excel con claves SCADA y tags."); return

    dominio = "CC"
    respaldo_map = {"ITCO": "TRA", "TRA": "ITCO", "REPS": "REPP", "REPP": "REPS"}
    respaldo = respaldo_map.get(empresa.upper())
    empresa_principal = empresa.upper()

    # ---------- Botones / estado ----------
    botones: list[tk.Button] = [b for b in (
        getattr(app, "boton_validar_tag_hsh", None),
        getattr(app, "boton_crear_tag_hsh", None),
    ) if b]

    origen_btn = getattr(app, "boton_validar_tag_hsh" if origin == "validar" else
                         ("boton_crear_tag_hsh" if origin == "crear" else ""), None)

    if aplicar and not messagebox.askyesno("Confirmar insercion", "Insertar tags en HSH?", parent=app.ventana):
        return

    servidor_principal: Optional[str] = app.generar_server(empresa, dominio)
    if not servidor_principal:
        messagebox.showerror("Error", "No se pudo resolver el servidor para la empresa."); return

    servidor_respaldo = app.generar_server(respaldo, dominio) if respaldo else None

    # Mapa auxiliar de servidores (para derivar prefijos PI / SCA-HIS)
    server_map: Dict[str, Optional[str]] = {empresa.upper(): servidor_principal}
    if respaldo and servidor_respaldo:
        server_map[respaldo.upper()] = servidor_respaldo

    # Targets de ejecucion del script de crear/validar
    run_targets: list[tuple[str, Optional[str], str]] = [(empresa, respaldo, servidor_principal)]
    if aplicar and respaldo:
        if not servidor_respaldo:
            messagebox.showerror("Error", f"No se pudo resolver el servidor respaldo para {respaldo}.", parent=app.ventana)
            return
        run_targets.append((respaldo, empresa, servidor_respaldo))
        server_map[respaldo.upper()] = servidor_respaldo

    env, cwd = app.secure_env(), app.base_dir

    # ---------- Utils UI ----------
    def _ui(fn):
        try: app.ventana.after(0, fn)
        except Exception: pass

    def _console(msg: str, tag: str = "info"):
        if getattr(app, "console", None): _ui(lambda: app.console.write(msg, tag))

    if getattr(app, "console", None): app.console.clear()
    app.start_status("Preparando validaciones HSH/SCADA...", indeterminate=True)
    for b in botones:
        try: b.config(state="disabled")
        except Exception: pass
    if origen_btn:
        try: origen_btn.config(text=" Procesando... ")
        except Exception: pass

    # ---------- Recolectores de salidas ----------
    report_paths: list[str] = []
    extra_paths: list[str] = []
    inserted_keys_full: dict[str, set[str]] = {}             # EMPRESA -> { 24001004.Value, ... }
    inserted_keys_map: Dict[str, Dict[str, Set[str]]] = {}   # EMPRESA -> base_key -> {SUFIJOS}
    verification_counts = {"ok": 0, "failed": 0}
    inserted_tags_full: Dict[str, Set[str]] = {}             # EMPRESA -> { TAG1, TAG2, ... }
    apply_import_servers: dict[str, str] = {}                # EMPRESA -> host SCADA observado en apply
    hsh_servers_used: Dict[str, str] = {}                    # EMPRESA -> servidor HSH utilizado
    current_empresa_crear: Optional[str] = None
    last_sca_host_seen: Optional[str] = None
    pi_snapshot_map: Dict[str, List[Dict[str, str]]] = {}
    pi_missing_tags_map: Dict[str, List[str]] = {}
    pi_snapshot_collected_at: Optional[str] = None
    pi_snapshot_messages: List[str] = []
    verification_failed = False
    total_rows: int = 0
    ready_rows: int = 0
    discarded_rows: int = 0

    def _collect_path(prefix: str, target: list[str], candidate: str):
        if not candidate: return
        if not os.path.isabs(candidate): candidate = os.path.normpath(os.path.join(cwd, candidate))
        if candidate not in target: target.append(candidate)

    def _restore_buttons():
        for b in botones:
            try:
                default_text = " Crear " if b is getattr(app, "boton_crear_tag_hsh", None) else " Validar "
                b.config(text=default_text, state="normal")
            except Exception: pass

    def _on_progress_crear(line: str):
        nonlocal total_rows, ready_rows, discarded_rows
        nonlocal last_sca_host_seen, current_empresa_crear
        line = (line or "").strip()
        if not line: return

        # Marcas del script
        if line.startswith("REPORT_PATH:"): _collect_path("REPORT_PATH:", report_paths, line.split(":",1)[1].strip())
        elif line.startswith("INFO_PATH:"): _collect_path("INFO_PATH:", extra_paths, line.split(":",1)[1].strip())
        elif line.startswith("QUERY_PATH:"): _collect_path("QUERY_PATH:", extra_paths, line.split(":",1)[1].strip())
        elif line.startswith("Intentando conexion:"):
            try:
                seg = line.split("SCA=", 1)[1]
                sca_host = seg.split("->", 1)[0].strip()
                last_sca_host_seen = sca_host
                if current_empresa_crear:
                    apply_import_servers[current_empresa_crear] = sca_host
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
                    server_map[emp_key] = ssh_host
            except ValueError:
                pass
        elif line.startswith("APPLY_KEYS:"):
            try:
                _, payload = line.split("APPLY_KEYS:", 1); emp_part, keys_part = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                keys = [k.strip() for k in keys_part.split(",") if k.strip()]
                if keys:
                    inserted_keys_full.setdefault(emp_key, set()).update(keys)
                    base_map = inserted_keys_map.setdefault(emp_key, {})
                    for full_key in keys:
                        base, dot, suffix = full_key.partition('.')
                        base_map.setdefault(base, set()).add(suffix if dot else '')
            except ValueError: pass
        elif line.startswith("APPLY_TAGS:"):
            try:
                _, payload = line.split("APPLY_TAGS:", 1); emp_part, tags_part = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                tags = [t.strip() for t in tags_part.split(",") if t.strip()]
                if tags: inserted_tags_full.setdefault(emp_key, set()).update(tags)
            except ValueError: pass
        elif line.startswith("APPLY_OK:"):
            try:
                _, payload = line.split("APPLY_OK:", 1)
                emp_part, _ = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                if last_sca_host_seen:
                    apply_import_servers[emp_key] = last_sca_host_seen
            except Exception:
                pass

        # Estadísticas de filas (salida de scripts.hsh_crear_tag)
        if line.startswith("Total registros:"):
            try:
                _, payload = line.split("Total registros:", 1)
                total_rows = int(payload.strip())
            except Exception:
                pass
        elif line.startswith("Listos:"):
            try:
                # Formato esperado: "Listos: X | Descartados: Y"
                _, payload = line.split("Listos:", 1)
                partes = payload.split("|", 1)
                if partes:
                    ready_rows = int(partes[0].strip().split()[0])
                if len(partes) > 1 and "Descartados" in partes[1]:
                    discarded_rows = int(partes[1].split("Descartados:", 1)[1].strip())
            except Exception:
                pass

        # Estatus UI / consola
        lower = line.lower(); tag = "info"
        if any(w in lower for w in ("error", "failed", "traceback")):
            tag = "error"; _ui(lambda: app.error_status(f"[CREAR TAG] {line}"))
        elif "warn" in lower or "warning" in lower: tag = "warn"
        elif any(token in lower for token in ("%", "...", "procesando", "validando", "insertando")):
            _ui(lambda: app.set_status(f"[CREAR TAG] {line}"))
        _console(f"[CREAR TAG] {line}", tag)

    # ---------- Estado de verificacion (scope superior; visible a todas las funciones) ----------
    verification_status: Dict[str, Dict[str, Dict[str, object]]] = {}
    verification_order: List[str] = []

    def _ensure_status(emp: str) -> Dict[str, Dict[str, object]]:
        emp_u = emp.upper()
        if emp_u not in verification_status:
            verification_status[emp_u] = {s: {"ok": None, "messages": []} for s in ("import","convert","dump","scada","pi")}
            verification_order.append(emp_u)
        return verification_status[emp_u]

    def _record_status(emp: str, step: str, ok: Optional[bool] = None, message: Optional[str] = None) -> None:
        s = _ensure_status(emp).get(step)
        if not s: return
        if ok is not None:
            current = s.get("ok")
            if current is None:
                s["ok"] = ok
            elif current and not ok:
                s["ok"] = False
            s["messages"] = []
        if message:
            msgs: List[str] = s.setdefault("messages", [])  # type: ignore[assignment]
            if message not in msgs: msgs.append(message)

    def _build_summary() -> List[str]:
        lines: List[str] = []
        for emp in verification_order:
            status = verification_status.get(emp, {})
            lines.append(f"{emp}:")

            dump_msgs = status.get("dump", {}).get("messages") if status else None
            if dump_msgs:
                for msg in dump_msgs:
                    lines.append(f"  - {msg}")
            else:
                lines.append("  - LookupTables: sin informacion")

            pi_msgs = status.get("pi", {}).get("messages") if status else None
            if pi_msgs:
                for msg in pi_msgs:
                    parts = [part.strip() for part in msg.split("|") if part.strip()]
                    if not parts:
                        continue
                    for part in parts:
                        lines.append(f"  - {part}")
            else:
                lines.append("  - Valores en PI: sin informacion")

            # Si hubo errores en import/convert/scada, incluirlos explicitamente
            for step, label in (("import", "Import HSH"), ("convert", "Convert HSH"), ("scada", "Actualizacion SCADA")):
                st = status.get(step)
                if not st:
                    continue
                if st.get("ok") is False:
                    detail = "; ".join(st.get("messages") or [])
                    lines.append(f"  - {label}: ERROR{(': ' + detail) if detail else ''}")

            lines.append("")

        while lines and not lines[-1]:
            lines.pop()
        return lines

    # ---------- Aux: Paths HSH locales ----------
    def _lookup_paths_for(emp: str) -> List[Path]:
        return list({Path(cwd) / "out" / emp.upper() / "HSH" / "lookup_table.csv",
                     Path(app.base_dir) / "out" / emp.upper() / "HSH" / "lookup_table.csv"})

    def _check_local_keys(emp: str, keys: List[str]) -> Tuple[List[str], List[str]]:
        existing: Set[str] = set()
        for path in _lookup_paths_for(emp):
            if not path.exists(): continue
            try:
                with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
                    for row in csv.DictReader(fh):
                        val = (row.get("key") or row.get("Key") or "").strip()
                        if val: existing.add(val)
            except Exception as exc:
                _console(f"[VERIFICAR] {emp} no se pudo leer {path}: {exc}", "warn")
        return [k for k in keys if k in existing], [k for k in keys if k not in existing]

    def _base_keys(keys: List[str]) -> List[str]:
        return sorted({k.partition('.')[0] for k in keys})

    def _count_created_tags() -> int:
        total = 0
        for bases in inserted_keys_map.values():
            total += len(bases)
        return total

    def _count_base_keys_from_list(keys: List[str]) -> int:
        return len(_base_keys(keys))

    def _pi_value_line(emp: str, tag: str) -> str:
        tag_clean = tag.strip()
        if not tag_clean:
            return ""
        rows = pi_snapshot_map.get(emp, [])
        tag_upper = tag_clean.upper()
        for row in rows or []:
            name = str(row.get("Name") or "").strip()
            if name.upper() == tag_upper:
                value = row.get("Value")
                value_txt = str(value) if value not in (None, "") else ""
                if not value_txt:
                    value_txt = "OK"
                return f"{tag_clean} = {value_txt}"
        missing = {t.upper() for t in (pi_missing_tags_map.get(emp, []) or [])}
        if tag_upper in missing:
            return ""
        return ""

    def _build_company_pi_lines(emp: str) -> List[str]:
        tags = sorted(inserted_tags_full.get(emp, []))
        if not tags:
            return []
        lines: List[str] = []
        for tag in tags:
            line = _pi_value_line(emp, tag)
            if line:
                lines.append(line)
        return lines

    # ---------- Derivar prefijos para SCA/HIS a partir de server hints / company_prefixes ----------
    def _derive_prefixes(empresa_u: str) -> List[str]:
        prefs: List[str] = []
        hint = server_map.get(empresa_u)
        if hint:
            lowered = hint.lower()
            cut = None
            for marker in ("sca","qds","his"):
                if marker in lowered: cut = lowered.index(marker); break
            pref = hint[:cut] if cut is not None else hint
            if pref: prefs.append(pref)
        for pref in (company_prefixes(empresa_u) or []):
            if pref and pref not in prefs: prefs.append(pref)
        return [p for p in prefs if p]

        # ---------- PI snapshot ----------
    def _collect_pi_snapshots() -> Tuple[List[str], bool]:
        nonlocal pi_snapshot_map, pi_snapshot_collected_at, pi_snapshot_messages, pi_missing_tags_map

        tags_por_empresa = {emp: set(tags) for emp, tags in inserted_tags_full.items() if tags}
        result = collect_pi_snapshots(
            app=app,
            tags_by_empresa=tags_por_empresa,
            server_map=server_map,
            console_write=lambda msg, tag='info': _console(msg, tag),
            record_status=_record_status,
            empresa_principal=empresa_principal,
            derive_prefixes=_derive_prefixes,
            pi_server_map={'ITCO': 'PI-CO-ITCOTRA01', 'TRA': 'PI-CO-ITCOTRA01', 'REPS': 'PI-CO-ITCOTRA01', 'REPP': 'PI-CO-ITCOTRA01'},
        )

        pi_snapshot_map.clear()
        pi_snapshot_map.update(result.snapshot_map)
        pi_missing_tags_map.clear()
        pi_missing_tags_map.update(result.missing_map)
        pi_snapshot_messages.clear()
        pi_snapshot_messages.extend(result.messages)
        pi_snapshot_collected_at = result.collected_at

        if empresa_principal not in pi_snapshot_map:
            pi_snapshot_map[empresa_principal] = []
        if empresa_principal not in pi_missing_tags_map:
            pi_missing_tags_map[empresa_principal] = []

        return result.lines, result.has_failures

    # ---------- SCADA bits ----------
    def _apply_scada_updates() -> Tuple[List[str], bool]:
        updates: List[str] = []; has_fail = False
        if sshserver is None:
            msg = "SCADA: sshserver no disponible en este entorno"
            updates.append(msg)
            for emp in inserted_keys_map.keys(): _record_status(emp, "scada", False, msg)
            return updates, True

        env_secure = app.secure_env(); prev_env = {k: os.environ.get(k) for k in env_secure}; os.environ.update(env_secure)
        log_dir = Path(app.base_dir) / "out" / "log"; log_dir.mkdir(parents=True, exist_ok=True)
        logger = logger_console = None
        if Logger is not None:
            logger, logger_console = Logger.initlog(str(log_dir / "scada_dbset.log"))

        def _log(level: str, message: str):
            log_tag = "info" if level == "info" else ("warn" if level in ("warn", "warning") else "error")
            _console(f"[SCADA] {message}", log_tag)
            if Logger is not None and logger is not None:
                level_normalized = "warning" if level == "warn" else level
                Logger.write_log().log_all(level_normalized, f"[SCADA] {message}", logger_console, logger)

        for emp_u, bases in inserted_keys_map.items():
            if not bases:
                continue

            # Construir lista de hosts candidatos (CC / QA) para la empresa
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

            if not (domain_hosts["CC"] or domain_hosts["QA"]):
                msg = f"{emp_u} SCADA: no se encontraron servidores configurados"
                updates.append(msg)
                _record_status(emp_u, "scada", False, msg)
                continue

            selected_hosts: List[Tuple[str, str]] = []

            # Elegir UN CC online (si existe)
            def _pick_online_for_domain(domain_label: str) -> Optional[Tuple[str, str]]:
                hosts = sorted(domain_hosts.get(domain_label, set()))
                for host in hosts:
                    label = f"{emp_u} {domain_label}"
                    client = None
                    try:
                        _log("info", f"Conectando a SCADA {label} ({host})...")
                        client = sshserver(host, logger, logger_console)
                        if client is None:
                            raise RuntimeError("sshserver retorno None")
                        _log("info", f"Conexion establecida con {host}")
                        _record_status(emp_u, "scada", None, f"Conexion establecida con {label}")
                        host_online = None
                        if scada_online is not None:
                            try:
                                host_online = scada_online(client, logger, logger_console)
                            except Exception as exc:
                                _log("warn", f"{label}: error verificando estado ONLINE ({exc})")
                        if scada_online is not None and not host_online:
                            msg = f"SCADA {label}: sin estado ONLINE; se omiten updates para este host."
                            updates.append(msg)
                            _log("warn", msg)
                            _record_status(emp_u, "scada", False, msg)
                            continue
                        if host_online:
                            _log("info", f"{label}: estado ONLINE detectado ({host_online}).")
                        return label, host
                    except Exception as exc:
                        msg = f"SCADA {label}: no se pudo conectar a {host}: {exc}"
                        updates.append(msg)
                        _log("error", msg)
                        _record_status(emp_u, "scada", False, msg)
                    finally:
                        try:
                            if client is not None:
                                client.close()
                        except Exception:
                            pass
                return None

            cc_selected = _pick_online_for_domain("CC")
            if cc_selected:
                selected_hosts.append(cc_selected)
            else:
                msg = f"{emp_u} SCADA: no se encontro ningun CC ONLINE para aplicar cambios."
                updates.append(msg)
                _log("error", msg)
                has_fail = True
                _record_status(emp_u, "scada", False, msg)

            # Elegir QADS (QA): se asume único y siempre online, pero se verifica una vez
            qa_hosts = sorted(domain_hosts.get("QA", set()))
            if qa_hosts:
                host = qa_hosts[0]
                label = f"{emp_u} QA"
                client = None
                try:
                    _log("info", f"Conectando a SCADA {label} ({host})...")
                    client = sshserver(host, logger, logger_console)
                    if client is None:
                        raise RuntimeError("sshserver retorno None")
                    _log("info", f"Conexion establecida con {host}")
                    _record_status(emp_u, "scada", None, f"Conexion establecida con {label}")
                    host_online = None
                    if scada_online is not None:
                        try:
                            host_online = scada_online(client, logger, logger_console)
                        except Exception as exc:
                            _log("warn", f"{label}: error verificando estado ONLINE ({exc})")
                    if scada_online is not None and not host_online:
                        msg = f"SCADA {label}: sin estado ONLINE; se omiten updates para QADS."
                        updates.append(msg)
                        _log("warn", msg)
                        _record_status(emp_u, "scada", False, msg)
                    else:
                        if host_online:
                            _log("info", f"{label}: estado ONLINE detectado ({host_online}).")
                        selected_hosts.append((label, host))
                except Exception as exc:
                    msg = f"SCADA {label}: no se pudo conectar a {host}: {exc}"
                    updates.append(msg)
                    _log("error", msg)
                    has_fail = True
                    _record_status(emp_u, "scada", False, msg)
                finally:
                    try:
                        if client is not None:
                            client.close()
                    except Exception:
                        pass

            if not selected_hosts:
                # No hay ningún host donde aplicar cambios
                continue

            # Aplicar dbset en todos los hosts seleccionados (CC online y QADS)
            for label, host in selected_hosts:
                client = None
                try:
                    _log("info", f"[{label}] Reabriendo conexion para aplicar bits ({host})...")
                    client = sshserver(host, logger, logger_console)
                    if client is None:
                        raise RuntimeError("sshserver retorno None")
                    for base_key, suffixes in bases.items():
                        suf = {s.upper() for s in suffixes if s}
                        bit_specs: Set[Tuple[int, int]] = set()
                        if "ESTIMATED" in suf:
                            bit_specs.add((5, 2))
                        elif suf & {"VALUE"}:
                            bit_specs.add((5, 1))
                        else:
                            bit_specs.add((4, 1))
                        for tipo, bit in sorted(bit_specs):
                            cmd = f". ~/.bash_profile && dbset -k 10 {tipo} 12 {base_key} {bit} = 1"
                            _log("info", f"[{label}] Ejecutando: {cmd}")
                            try:
                                stdin, stdout, stderr = client.exec_command(cmd)
                                rc = stdout.channel.recv_exit_status()
                                if rc == 0:
                                    msg = f"SCADA {label}: OK {base_key} bit {bit}"
                                    updates.append(msg)
                                    _log("info", msg)
                                    _record_status(emp_u, "scada", True, msg)
                                else:
                                    err = stderr.read().decode("utf-8", "ignore").strip()
                                    msg = f"SCADA {label}: fallo {base_key} bit {bit} (rc={rc}) {err}"
                                    updates.append(msg)
                                    _log("error", msg)
                                    has_fail = True
                                    _record_status(emp_u, "scada", False, msg)
                            except Exception as exc:
                                msg = f"SCADA {label}: error {base_key} bit {bit}: {exc}"
                                updates.append(msg)
                                _log("error", msg)
                                has_fail = True
                                _record_status(emp_u, "scada", False, msg)
                except Exception as exc:
                    msg = f"SCADA {label}: error general aplicando bits: {exc}"
                    updates.append(msg)
                    _log("error", msg)
                    has_fail = True
                    _record_status(emp_u, "scada", False, msg)
                finally:
                    try:
                        if client is not None:
                            client.close()
                            _log("info", f"Conexion cerrada con {host}")
                    except Exception:
                        pass

        for k, v in prev_env.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        return updates, has_fail

    # ---------- Reporte PI a archivos ----------
    def _append_pi_snapshots_to_reports(summary: Optional[List[str]]) -> None:
        if not extra_paths: return
        if not pi_snapshot_map and not pi_snapshot_messages: return
        section: List[str] = ["", "Valores en PI"]
        rows = pi_snapshot_map.get(empresa_principal, [])
        if rows:
            section.extend([f"- {r.get('Name','?')} = {r.get('Value','?')}" for r in rows])
        else:
            section.append("- Sin valores consultados.")
        missing = [t for t in pi_missing_tags_map.get(empresa_principal, []) if t]
        if missing:
            section.append("Sin datos: " + ", ".join(missing))
        appended = False
        for p in extra_paths:
            try:
                if p.lower().endswith("informe_crear_tag.txt") and os.path.exists(p):
                    with open(p, "a", encoding="utf-8") as fh: fh.write("\n".join(section) + "\n")
                    appended = True
            except Exception as exc:
                _console(f"[PI] No se pudo actualizar {p}: {exc}", "warn")
        if appended: _console("[PI] Resumen de valores agregado a informe_crear_tag.txt", "info")

    def _append_verification_summary_to_reports(summary: Optional[List[str]]) -> None:
        if not summary: return
        txt_ok = xlsx_ok = False
        for p in extra_paths:
            try:
                if p.lower().endswith("informe_crear_tag.txt") and os.path.exists(p):
                    with open(p, "a", encoding="utf-8") as fh:
                        fh.write("\nResumen de verificacion:\n" + "\n".join(summary) + "\n\n")
                    txt_ok = True
            except Exception as exc:
                _console(f"[VERIFICACION] No se pudo actualizar {p}: {exc}", "warn")
        for p in report_paths:
            if not (p and p.lower().endswith(".xlsx") and os.path.exists(p)): continue
            if load_workbook is None:
                _console(f"[VERIFICACION] No se puede actualizar {p}: openpyxl no disponible", "warn"); continue
            try:
                wb = load_workbook(p); ws = wb["Verificacion"] if "Verificacion" in wb.sheetnames else wb.create_sheet("Verificacion")
                ws.delete_rows(1, ws.max_row)
                for i, line in enumerate(summary, start=1): ws.cell(row=i, column=1).value = line
                wb.save(p); xlsx_ok = True
            except Exception as exc:
                _console(f"[VERIFICACION] No se pudo actualizar {p}: {exc}", "warn")
        if txt_ok: _console("[VERIFICACION] Resumen agregado a informe_crear_tag.txt", "info")
        if xlsx_ok: _console("[VERIFICACION] Resumen agregado a reporte Excel", "info")

    # ---------- Finalizacion ----------
    def _finish(rc: int, error_message: str | None = None, verification_summary: Optional[List[str]] = None):
        def _end():
            _restore_buttons()
            try:
                app.stop_status()
            except Exception:
                pass
            _append_pi_snapshots_to_reports(verification_summary)
            _append_verification_summary_to_reports(verification_summary)

            archivos = [p for p in [*report_paths, *extra_paths] if p and os.path.exists(p)]
            created_tags = _count_created_tags()
            failed_tags = max(verification_counts.get("failed", 0), 0)

            if aplicar:
                resumen_text = "\n".join([
                    f"Tags creados: {created_tags}",
                    f"No aprobados: {failed_tags}",
                ])
            else:
                aprobados = max(ready_rows, 0)
                no_aprobados = max(total_rows - ready_rows, 0) if total_rows else 0
                resumen_text = "\n".join([
                    f"Tags aprobados: {aprobados}",
                    f"Tags no aprobados: {no_aprobados}",
                ])

            details: List[str] = []
            for emp in sorted(inserted_tags_full.keys()):
                company_lines = _build_company_pi_lines(emp)
                if not company_lines:
                    continue
                details.append(f"{emp}:")
                for line in company_lines:
                    details.append(f"  - {line}")
            if not details:
                details.append("Sin tags con valores PI disponibles.")

            if rc == 0:
                app.success_status("Proceso listo" if aplicar else "Validaciones listas")
                try:
                    if hasattr(app, "refresh_last_upd_hsh_crear"):
                        app.refresh_last_upd_hsh_crear()
                except Exception:
                    pass
                dialog_status = "success"
                dialog_title = "Crear Tag completado"
            else:
                app.error_status("El proceso termino con errores")
                dialog_status = "error"
                dialog_title = "Crear Tag con errores"
                if error_message:
                    details.insert(0, error_message)
                elif not details:
                    details.append("El proceso termino con errores. Revisa la consola.")

            show_summary_dialog(
                parent=app.ventana,
                mensaje=resumen_text or "Sin informacion disponible.",
                title=dialog_title,
                status=dialog_status,
                details=details or None,
                files=archivos or None,
                show_open_file=bool(archivos) and rc == 0,
            )

        _ui(_end)

    def _fail(msg: str): _console(f"[CREAR TAG] {msg}", "error"); _finish(1, msg)

    # ---------- Verificacion post-apply (import/convert + SCADA + PI) ----------
    def _start_verification():
        nonlocal verification_failed
        verify_queue: List[Tuple[str, str, List[str]]] = []

        def _complete(rc: int, message: Optional[str] = None):
            summary = _build_summary()
            for line in summary:
                if not line: continue
                _console(f"[VERIFICACION] {line}", "error" if "ERROR" in line.upper() else "info")
            if rc != 0 and not message: message = "Verificacion HSH detecto inconsistencias"
            _finish(rc, message, summary if summary else None)

        for target_empresa, _respaldo, target_server in run_targets:
            emp_u = target_empresa.upper()
            preferred_server = apply_import_servers.get(emp_u, target_server)
            keys = sorted(inserted_keys_full.get(emp_u, set()))
            if keys:
                verify_queue.append((target_empresa, preferred_server, keys))
                _record_status(emp_u, "dump", None, f"LookupTables pendientes: {len(keys)} tag(s)")
            else:
                _record_status(emp_u, "dump", None, "LookupTables: sin tags nuevos")

        if not verify_queue:
            if aplicar:
                scada_lines, scada_failed = _apply_scada_updates()
                if scada_failed:
                    verification_failed = True
                    _complete(1)
                    return
                if ENABLE_PI_CHECKS and inserted_keys_map:
                    _console("[PI] esperando 10 segundos antes de consultar valores", "info")
                    time.sleep(10)
                    pi_lines, pi_failed = _collect_pi_snapshots()
                    if pi_failed:
                        verification_failed = True
                        _complete(1)
                        return
            _complete(0); return

        def _verify_next():
            nonlocal verification_failed
            if not verify_queue:
                if aplicar:
                    scada_lines, scada_failed = _apply_scada_updates()
                    if scada_failed:
                        verification_failed = True
                    elif ENABLE_PI_CHECKS:
                        pi_lines, pi_failed = _collect_pi_snapshots()
                        if pi_failed:
                            verification_failed = True
                _complete(1 if verification_failed else 0); return

            emp, server, keys = verify_queue.pop(0)
            _ui(lambda: app.set_status(f"Reimportando HSH ({emp})..."))
            import_cmd = build_cmd("scripts.importar_all", server, emp, "hsh", "--usecase", "hsh_crear_tag")
            app.tasks.run_subprocess(import_cmd, env=env, cwd=cwd, on_progress=_on_progress_crear,
                                     on_done=lambda rc, e=emp, s=server, k=keys: _after_import_verify(rc, e, s, k))

        def _after_import_verify(rc: int, emp: str, server: str, keys: List[str]):
            nonlocal verification_failed
            emp_u = emp.upper()
            if rc != 0:
                _console(f"[VERIFICAR] {emp} import HSH fallo (rc={rc})", "error")
                verification_counts["failed"] += _count_base_keys_from_list(keys)
                verification_failed = True; _record_status(emp_u, "import", False, f"Import HSH fallo (rc={rc})")
                while verify_queue: verify_queue.pop()
                _complete(1); return
            _record_status(emp_u, "import", True, "Import HSH OK")
            _ui(lambda: app.set_status(f"Convirtiendo HSH ({emp})..."))
            convert_cmd = build_cmd("scripts.Convertir_all", emp, "Validar_HSH", "--only", "hsh")
            app.tasks.run_subprocess(convert_cmd, env=env, cwd=cwd, on_progress=_on_progress_crear,
                                     on_done=lambda rc, e=emp, k=keys: _after_convert_verify(rc, e, k))

        def _after_convert_verify(rc: int, emp: str, keys: List[str]):
            nonlocal verification_failed
            emp_u = emp.upper()
            if rc != 0:
                _console(f"[VERIFICAR] {emp} conversion HSH fallo (rc={rc})", "error")
                verification_counts["failed"] += _count_base_keys_from_list(keys)
                verification_failed = True; _record_status(emp_u, "convert", False, f"Conversion HSH fallo (rc={rc})")
                while verify_queue: verify_queue.pop()
                _complete(1); return
            _record_status(emp_u, "convert", True, "Conversion HSH OK")
            present, missing = _check_local_keys(emp, keys)
            if missing:
                missing_bases = _base_keys(missing)
                verification_counts["failed"] += len(missing_bases)
                faltan_txt = ", ".join(missing_bases)
                _console(f"[VERIFICAR] {emp} LookupTables faltantes: {faltan_txt}", "error")
                verification_failed = True
                _record_status(emp_u, "dump", False, f"LookupTables faltantes: {faltan_txt}")
                while verify_queue: verify_queue.pop()
                _complete(1); return
            base_tags = _base_keys(present)
            verification_counts["ok"] += len(base_tags)
            if base_tags:
                base_txt = ", ".join(base_tags)
                msg = f"LookupTables verificados: {base_txt}"
            else:
                msg = "LookupTables: sin tags verificados"
            _console(f"[VERIFICAR] {emp} {msg}", "info")
            _record_status(emp_u, "dump", True, msg)
            _verify_next()

        _verify_next()

    # ---------- Runner principal (validar/crear) ----------
    def _run_crear_script():
        nonlocal current_empresa_crear, last_sca_host_seen
        queue = list(run_targets)

        def _run_next():
            nonlocal current_empresa_crear, last_sca_host_seen
            if not queue:
                if aplicar and any(inserted_keys_full.values()): _start_verification()
                else: _finish(0)
                return
            current_empresa, current_respaldo, current_server = queue.pop(0)
            accion = "Insertando" if aplicar else "Generando reporte"
            _ui(lambda: app.set_status(f"{accion} ({current_empresa})..."))
            current_empresa_crear = current_empresa.upper()
            last_sca_host_seen = None
            if current_empresa_crear and current_server:
                apply_import_servers[current_empresa_crear] = current_server
                hsh_servers_used[current_empresa_crear] = current_server
            cmd = build_cmd("scripts.hsh_crear_tag", current_empresa, "--input", excel_path)
            if current_respaldo: cmd += ["--respaldo", current_respaldo]
            if aplicar: cmd += ["--apply", "--server", current_server, "--skip-backup-insert"]
            _console(f">> CMD[CREAR-TAG:{current_empresa}]: {' '.join(map(str, cmd))}", "warn")
            def _on_done_crear(rc: int, emp=current_empresa):
                nonlocal current_empresa_crear
                current_empresa_crear = None
                if rc != 0:
                    _finish(rc, f"El proceso para {emp} termino con errores")
                else:
                    _run_next()
            app.tasks.run_subprocess(cmd, env=env, cwd=cwd, on_progress=_on_progress_crear, on_done=_on_done_crear)
        _run_next()

    # ---------- Pipeline de sincronizacion previa ----------
    def _run_update_pipeline():
        cmd_import_principal = build_cmd("scripts.importar_all", servidor_principal, empresa, "sca,hsh", "--usecase", "hsh_crear_tag")
        cmd_import_respaldo = (
            build_cmd("scripts.importar_all", servidor_respaldo, respaldo, "sca,hsh", "--usecase", "hsh_crear_tag")
            if respaldo and servidor_respaldo
            else None
        )
        cmd_conv_sca = build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "sca")
        cmd_conv_hsh = build_cmd("scripts.Convertir_all", empresa, "Validar_HSH", "--only", "hsh")
        cmd_conv_sca_res = build_cmd("scripts.Convertir_all", respaldo, "Validar_HSH", "--only", "sca") if respaldo else None
        cmd_conv_hsh_res = build_cmd("scripts.Convertir_all", respaldo, "Validar_HSH", "--only", "hsh") if respaldo else None

        if respaldo and not servidor_respaldo:
            _fail(f"No se pudo resolver el servidor respaldo para {respaldo}.")
            return

        def _run_convert_hsh_res():
            if not (respaldo and cmd_conv_hsh_res):
                _run_crear_script()
                return
            _ui(lambda: app.set_status(f"Convirtiendo HSH respaldo {respaldo}..."))
            _console(f">> CMD[CONVERT HSH respaldo]: {' '.join(map(str, cmd_conv_hsh_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_hsh_res,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_crear,
                on_done=lambda rc: (_run_crear_script() if rc == 0 else _fail(f"Conversion HSH respaldo ({respaldo}) fallo")),
            )

        def _run_convert_sca_res():
            if not (respaldo and cmd_conv_sca_res):
                _run_convert_hsh_res()
                return
            _ui(lambda: app.set_status(f"Convirtiendo SCADA respaldo {respaldo}..."))
            _console(f">> CMD[CONVERT SCADA respaldo]: {' '.join(map(str, cmd_conv_sca_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_sca_res,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_crear,
                on_done=lambda rc: (_run_convert_hsh_res() if rc == 0 else _fail(f"Conversion SCADA respaldo ({respaldo}) fallo")),
            )

        def _run_convert_hsh():
            _ui(lambda: app.set_status("Convirtiendo HSH principal..."))
            _console(f">> CMD[CONVERT HSH principal]: {' '.join(map(str, cmd_conv_hsh))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_hsh,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_crear,
                on_done=lambda rc: (_run_convert_sca_res() if rc == 0 else _fail("Conversion HSH principal fallo")),
            )

        def _run_convert_sca():
            _ui(lambda: app.set_status("Convirtiendo SCADA principal..."))
            _console(f">> CMD[CONVERT SCADA principal]: {' '.join(map(str, cmd_conv_sca))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_sca,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_crear,
                on_done=lambda rc: (_run_convert_hsh() if rc == 0 else _fail("Conversion SCADA principal fallo")),
            )

        def _run_import_res():
            if not cmd_import_respaldo:
                _run_convert_sca()
                return
            _ui(lambda: app.set_status(f"Sincronizando hsh_crear_tag respaldo ({respaldo})..."))
            _console(f">> CMD[IMPORT respaldo]: {' '.join(map(str, cmd_import_respaldo))}", "warn")
            app.tasks.run_subprocess(
                cmd_import_respaldo,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_crear,
                on_done=lambda rc: (_run_convert_sca() if rc == 0 else _fail("Importacion SCADA/HSH respaldo fallo")),
            )

        def _after_import_principal(rc: int):
            if rc != 0:
                _fail("Importacion SCADA/HSH principal fallo")
                return
            _run_import_res()

        _ui(lambda: app.set_status("Sincronizando hsh_crear_tag (SCADA+HSH)..."))
        _console(f">> CMD[IMPORT principal]: {' '.join(map(str, cmd_import_principal))}", "warn")
        app.tasks.run_subprocess(
            cmd_import_principal,
            env=env,
            cwd=cwd,
            on_progress=_on_progress_crear,
            on_done=_after_import_principal,
        )

    _run_update_pipeline()


def ejecutar_consulta_pi_hsh(app) -> None:
    """
    Ejecuta SOLO la consulta a PI usando:
    - Empresa seleccionada en la vista de Crear Tag.
    - Servidor resuelto via ServerResolver.
    - Tags generados en el último informe de Crear Tag (informe_crear_tag.txt).
    """
    empresa_var = getattr(app, "opcion_empresa_hsh_crear", None)
    if not empresa_var:
        messagebox.showerror("Consultar PI", "No se encontró configuración para esta vista.")
        return

    empresa = (empresa_var.get() or "").strip()
    if not empresa or empresa == "Empresa...":
        messagebox.showerror("Consultar PI", "Selecciona una empresa.")
        return

    empresa_principal = empresa.upper()

    info_dir = Path(output_root()).resolve() / "out" / "crear_tag"
    info_path = info_dir / "informe_crear_tag.txt"
    if not info_path.exists():
        messagebox.showerror(
            "Consultar PI",
            "No se encontró informe de Crear Tag (informe_crear_tag.txt).\n\n"
            "Ejecuta primero Validar o Crear Tag HSH.",
        )
        return

    tags: Set[str] = set()
    try:
        lines = info_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as exc:
        messagebox.showerror("Consultar PI", f"No se pudo leer el informe de Crear Tag:\n{exc}")
        return

    in_pairs_section = False
    for line in lines:
        raw = line.strip()
        if not raw:
            if in_pairs_section:
                break
            continue
        if raw.startswith("Pairs generados"):
            in_pairs_section = True
            continue
        if in_pairs_section and raw.startswith("-"):
            try:
                _, payload = raw.split("-", 1)
                _, tag_part = payload.split(",", 1)
                tag = tag_part.strip()
                if tag:
                    tags.add(tag)
            except ValueError:
                continue

    if not tags:
        messagebox.showwarning(
            "Consultar PI",
            "El último informe de Crear Tag no contiene tags generados para consultar en PI.",
        )
        return

    dominio = "CC"
    servidor_principal: Optional[str] = app.generar_server(empresa, dominio)
    if not servidor_principal:
        messagebox.showerror(
            "Consultar PI",
            "No se pudo resolver el servidor para la empresa seleccionada.",
        )
        return

    server_map: Dict[str, Optional[str]] = {empresa_principal: servidor_principal}

    def _console(msg: str, tag: str = "info") -> None:
        if getattr(app, "console", None):
            try:
                app.ventana.after(0, lambda: app.console.write(msg, tag))
            except Exception:
                pass

    def _derive_prefixes(empresa_u: str) -> List[str]:
        prefs: List[str] = []
        hint = server_map.get(empresa_u)
        if hint:
            lowered = hint.lower()
            cut = None
            for marker in ("sca", "qds", "his"):
                if marker in lowered:
                    cut = lowered.index(marker)
                    break
            pref = hint[:cut] if cut is not None else hint
            if pref:
                prefs.append(pref)
        for pref in (company_prefixes(empresa_u) or []):
            if pref and pref not in prefs:
                prefs.append(pref)
        return [p for p in prefs if p]

    app.start_status("Consultando valores en PI...", indeterminate=True)

    try:
        result = collect_pi_snapshots(
            app=app,
            tags_by_empresa={empresa_principal: tags},
            server_map=server_map,
            console_write=lambda msg, tag="info": _console(msg, tag),
            record_status=None,
            empresa_principal=empresa_principal,
            derive_prefixes=_derive_prefixes,
            pi_server_map={
                "ITCO": "PI-CO-ITCOTRA01",
                "TRA": "PI-CO-ITCOTRA01",
                "REPS": "PI-CO-ITCOTRA01",
                "REPP": "PI-CO-ITCOTRA01",
            },
        )
    finally:
        try:
            app.stop_status()
        except Exception:
            pass

    status = "success" if not result.has_failures else "error"
    resumen = f"Empresa: {empresa_principal}\nTags consultados: {len(tags)}"

    details: List[str] = []
    if result.lines:
        details.extend(result.lines)
    elif result.missing_lines:
        details.append("Tags sin datos o con errores:")
        details.extend(result.missing_lines)
    else:
        details.append("No se recibieron datos desde PI. Revisa la consola y pi_query.log.")

    show_summary_dialog(
        parent=app.ventana,
        mensaje=resumen,
        title="Consulta PI - Crear Tag",
        status=status,
        details=details or None,
        files=None,
        show_open_file=False,
    )


__all__ = ["ejecutar_crear_tag_hsh", "ejecutar_consulta_pi_hsh"]

