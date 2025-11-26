from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

from ui.components.dialogs import make_modal
from utils.shell import open_in_file_manager, open_path
from .common import (
    Logger,
    build_cmd,
    collect_pi_snapshots,
    messagebox,
    show_summary_dialog,
    sshserver,
    scada_online,
    SCADA_HOSTS_FULL,
    tk,
    Workbook,
)


def ejecutar_cambiar_key_hsh(app, aplicar: bool = False, origin: str | None = None) -> None:
    """
    Orquesta el flujo de cambio de SCADA Key:
    1. Apagar los bits de la key actual en todos los dominios.
    2. Modificar lookup_tables en Mongo para la empresa principal y su respaldo.
    3. Generar Delete/Purge y validar manualmente la eliminacion.
    4. Encender los bits de la key nueva en todos los dominios.
    5. Consultar PI con tags especificos asociados a las keys nuevas.
    """
    ventana = getattr(app, "ventana", None)

    empresa_var = getattr(app, "opcion_empresa_hsh_cambiar", None)
    if not empresa_var:
        messagebox.showerror("Error", "No se encontro configuracion de empresas para esta vista.", parent=ventana)
        return

    empresa = (empresa_var.get() or "").strip().upper()
    if not empresa or empresa == "EMPRESA...":
        messagebox.showerror("Error", "Selecciona una empresa.", parent=ventana)
        return

    excel_path = getattr(app, "hsh_cambiar_key_file", None)
    if not excel_path or not os.path.isfile(excel_path):
        messagebox.showerror("Error", "Selecciona el archivo Excel con las claves a cambiar.", parent=ventana)
        return

    dominio = "CC"
    respaldo_map = {"ITCO": "TRA", "TRA": "ITCO", "REPS": "REPP", "REPP": "REPS"}
    respaldo = respaldo_map.get(empresa)

    servidor_principal = app.generar_server(empresa, dominio)
    if not servidor_principal:
        messagebox.showerror("Error", "No se pudo resolver el servidor principal para la empresa seleccionada.", parent=ventana)
        return

    servidor_respaldo = app.generar_server(respaldo, dominio) if respaldo else None
    if aplicar and respaldo and not servidor_respaldo:
        messagebox.showerror(
            "Error",
            f"No se pudo resolver el servidor respaldo para {respaldo}. No es posible continuar.",
            parent=ventana,
        )
        return

    botones: List[tk.Button] = [
        getattr(app, "boton_validar_cambiar_key_hsh", None),
        getattr(app, "boton_cambiar_key_hsh", None),
    ]
    botones = [b for b in botones if b is not None]

    def _restore_buttons():
        for boton in botones:
            try:
                boton.config(state="normal")
                if boton is getattr(app, "boton_validar_cambiar_key_hsh", None):
                    boton.config(text=" Validar ")
                elif boton is getattr(app, "boton_cambiar_key_hsh", None):
                    boton.config(text=" Cambiar ")
            except Exception:
                pass

    def _disable_buttons():
        for boton in botones:
            try:
                boton.config(state="disabled")
            except Exception:
                pass
        target = getattr(app, "boton_validar_cambiar_key_hsh", None if origin != "validar" else "placeholder")
        if origin == "validar" and isinstance(target, tk.Button):
            target.config(text=" Validando... ")
        target = getattr(app, "boton_cambiar_key_hsh", None if origin != "cambiar" else "placeholder")
        if origin == "cambiar" and isinstance(target, tk.Button):
            target.config(text=" Cambiando... ")

    def _ui(callable_):
        try:
            app.ventana.after(0, callable_)
        except Exception:
            try:
                callable_()
            except Exception:
                pass

    console = getattr(app, "console", None)

    log_dir = Path(app.base_dir) / "out" / "log"
    logger_main = logger_console_main = None
    log_path = str(log_dir / "hsh_cambiar_key.log")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if Logger is not None:
        try:
            logger_main, logger_console_main = Logger.initlog(str(log_dir / "hsh_cambiar_key.log"))
        except Exception:
            logger_main = logger_console_main = None

    def _console(msg: str, tag: str = "info"):
        level = "info"
        tag_lower = (tag or "").lower()
        if "error" in tag_lower:
            level = "error"
        elif "warn" in tag_lower:
            level = "warn"
        elif "success" in tag_lower:
            level = "info"
        if Logger is not None and logger_main is not None:
            try:
                Logger.write_log().log_all(level, msg, logger_console_main, logger_main)
            except Exception:
                pass
        if console is None:
            return
        def _write():
            try:
                console.write(msg, tag)
            except Exception:
                pass
        _ui(_write)

    def _set_status(msg: str, kind: str = "info", indeterminate: bool = False):
        if kind == "info":
            _ui(lambda: app.set_status(msg))
        elif kind == "error":
            _ui(lambda: app.error_status(msg))
        elif kind == "success":
            _ui(lambda: app.success_status(msg))
        if indeterminate:
            _ui(lambda: app.start_status(msg, indeterminate=True))

    _disable_buttons()
    _set_status("Preparando cambio de SCADA Key...", indeterminate=True)

    env = app.secure_env()
    cwd = app.base_dir

    # Estado
    state: Dict[str, object] = {
        "empresa": empresa,
        "respaldo": respaldo,
        "servidor_principal": servidor_principal,
        "servidor_respaldo": servidor_respaldo,
        "excel": excel_path,
        "apply": aplicar,
        "delete_files": [],
        "purge_files": [],
        "report_paths": [],
        "info_paths": [],
        "query_paths": [],
        "pending_keys": set(),
        "mongo_summary": [],
        "scada_disable": [],
        "scada_enable": [],
        "pi_reports": [],
        "pi_missing": [],
        "script_errors": [],
        "pi_tags": {},
        "scada_pending": [],
        "script_messages": [],
        "changed_pairs": [],
        "verification_cycle": 0,
        "bits_apagados": False,
        "verification_status": {},
        "applied_servers": {},
        "inserted_keys": {},
        "pi_snapshot_map": {},
        "pi_missing_map": {},
        "pi_snapshot_messages": [],
        "pi_snapshot_collected_at": None,
        "final_summary": [],
        "mongo_modifications": {
            "principal": {"empresa": empresa, "servidor": servidor_principal, "modificados": 0},
            "respaldo": {"empresa": respaldo, "servidor": servidor_respaldo, "modificados": 0} if respaldo else None
        },
        "scada_actions_completed": {
            "disable_principal": False,
            "disable_respaldo": False,
            "enable_principal": False,
            "enable_respaldo": False
        },
        "report_excel_path": None,
        "log_path": log_path,
    }

    # Exponer el estado bruto del flujo para posibles consultas PI posteriores
    try:
        app._cambiar_key_state = state  # type: ignore[attr-defined]
    except Exception:
        pass


    def _generate_report_excel() -> Optional[str]:
        state["report_excel_path"] = None
        state["report_paths"] = []
        state["info_paths"] = []
        if Workbook is None:
            _console("No se puede crear el reporte Excel: openpyxl no está disponible.", "error")
            return None

        empresa_root = (state.get("empresa") or "REPORTE").upper()
        report_dir = Path(app.base_dir) / "out" / "cambiar_key" / empresa_root
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            _console(f"[REPORT] No se pudo preparar el directorio de reportes: {exc}", "error")
            return None

        report_path = report_dir / "reporte_Cambiar_Key.xlsx"

        def _normalize_suffix(raw: str) -> Tuple[str, str]:
            token = (raw or "").strip()
            if not token:
                return "VALUE", "Value"
            token_upper = token.upper()
            if token_upper == "VALUE":
                return "VALUE", "Value"
            if token_upper == "ESTIMATED":
                return "ESTIMATED", "Estimated"
            if token_upper == "STATUS":
                return "STATUS", "Status"
            if token_upper in {"Q", "P"}:
                return token_upper, token_upper
            return token_upper, token

        def _split_tag_name(name: str) -> Tuple[str, str]:
            base = str(name or "").strip()
            suffix = ""
            if "." in base:
                base, suffix = base.rsplit(".", 1)
            return base, suffix

        def _derive_key_from_base(base: str) -> str:
            clean = base.strip()
            return clean.rsplit(":", 1)[0] if ":" in clean else clean

        suffix_order: List[str] = []
        suffix_labels: Dict[str, str] = {}

        def _register_suffix(raw: str) -> str:
            key, label = _normalize_suffix(raw)
            if key not in suffix_labels:
                suffix_labels[key] = label
                suffix_order.append(key)
            return key

        verification_rows: List[List[str]] = []
        verification = state.get("verification_status") or {}
        for emp in sorted(verification.keys()):
            categories = verification.get(emp) or {}
            for category in sorted(categories.keys()):
                for message in categories.get(category, []):
                    detail = str(message or "").strip()
                    status_text = ""
                    if ":" in detail:
                        head, tail = detail.rsplit(":", 1)
                        tail_clean = tail.strip()
                        if tail_clean.lower() in {"true", "false", "ok", "error", "si", "no", "pass", "fail"}:
                            detail = head.strip()
                            status_text = tail_clean
                    verification_rows.append([emp, category, detail, status_text])

        for entry in state.get("mongo_summary") or []:
            emp = ""
            detail = str(entry or "").strip()
            if ":" in detail:
                emp_part, rest = detail.split(":", 1)
                emp = emp_part.strip().upper()
                detail = rest.strip()
            verification_rows.append([emp, "mongo", detail, ""])

        if state.get("changed_pairs"):
            emp_principal = (state.get("empresa") or "").upper()
            for pair in state["changed_pairs"]:
                verification_rows.append([emp_principal, "keys", pair, ""])

        pi_entries: Dict[Tuple[str, str], Dict[str, object]] = {}

        def _entry(emp: str, base_tag: str) -> Dict[str, object]:
            key = (emp, base_tag)
            if key not in pi_entries:
                pi_entries[key] = {
                    "key": _derive_key_from_base(base_tag),
                    "tag": base_tag,
                    "values": {},
                    "expected": set(),
                }
            return pi_entries[key]

        for emp, tags in (state.get("pi_tags") or {}).items():
            emp_u = emp.upper()
            for tag in sorted(tags):
                base_tag, suffix_raw = _split_tag_name(tag)
                suffix_key = _register_suffix(suffix_raw)
                entry = _entry(emp_u, base_tag)
                entry["expected"].add(suffix_key)

        for emp, rows in (state.get("pi_snapshot_map") or {}).items():
            emp_u = emp.upper()
            for row in rows or []:
                name = str(row.get("Name") or "").strip()
                if not name:
                    continue
                base_tag, suffix_raw = _split_tag_name(name)
                suffix_key = _register_suffix(suffix_raw)
                entry = _entry(emp_u, base_tag)
                value_raw = row.get("Value")
                entry["values"][suffix_key] = "" if value_raw is None else str(value_raw)
                expected_set: Set[str] = entry["expected"]  # type: ignore[assignment]
                expected_set.discard(suffix_key)

        for emp, missing_tags in (state.get("pi_missing_map") or {}).items():
            emp_u = emp.upper()
            for tag in missing_tags or []:
                base_tag, suffix_raw = _split_tag_name(tag)
                suffix_key = _register_suffix(suffix_raw)
                entry = _entry(emp_u, base_tag)
                values: Dict[str, str] = entry["values"]  # type: ignore[assignment]
                values.setdefault(suffix_key, "No Data")
                expected_set = entry["expected"]  # type: ignore[assignment]
                expected_set.discard(suffix_key)

        if not suffix_order and pi_entries:
            suffix_order.append("VALUE")
            suffix_labels["VALUE"] = "Value"

        pi_headers = ["Empresa", "Key", "Tag"]
        pi_headers.extend(suffix_labels[key] for key in suffix_order)

        pi_rows: List[List[str]] = []
        for emp_base in sorted(pi_entries.keys()):
            emp, base_tag = emp_base
            entry = pi_entries[emp_base]
            key_name = entry["key"]  # type: ignore[index]
            expected_set = entry["expected"]  # type: ignore[index]
            values = entry["values"]  # type: ignore[index]
            row = [emp, key_name, base_tag]
            for suffix_key in suffix_order:
                if suffix_key in values:
                    row.append(values[suffix_key])
                elif suffix_key in expected_set:
                    row.append("No Data")
                else:
                    row.append("")
            pi_rows.append(row)

        try:
            workbook = Workbook()
        except Exception as exc:
            _console(f"[REPORT] No se pudo crear el Workbook: {exc}", "error")
            return None

        active = workbook.active
        if active is not None:
            workbook.remove(active)

        ws_ver = workbook.create_sheet("Verificaciones")
        ws_pi = workbook.create_sheet("PI")

        ws_ver.append(["Empresa", "Categoria", "Detalle", "Estado"])
        for data_row in verification_rows:
            ws_ver.append(data_row)

        ws_pi.append(pi_headers)
        for data_row in pi_rows:
            ws_pi.append(data_row)

        try:
            workbook.save(report_path)
        except Exception as exc:
            _console(f"[REPORT] No se pudo guardar el reporte Excel: {exc}", "error")
            return None

        state["report_excel_path"] = str(report_path)
        state["report_paths"] = [state["report_excel_path"]]
        state["info_paths"] = []
        _console(f"[REPORT] Reporte Excel generado: {report_path}", "info")
        return state["report_excel_path"]

    def _normalize_key_token(value: object) -> str:
        token = str(value or "").strip()
        if not token:
            return ""
        match = re.search(r"\d{5,}", token)
        if match:
            return match.group(0).upper()
        token = token.split("|")[-1].split("->")[0]
        token = token.split(":", 1)[-1] if ":" in token and token.split(":", 1)[0].upper() in {"ITCO", "TRA", "REPS", "REPP"} else token
        token = token.split(".", 1)[0]
        token = token.strip(" -:")
        return token.upper()

    def _collect_keys_from(value: object) -> Set[str]:
        result: Set[str] = set()
        if not value:
            return result
        if isinstance(value, (list, tuple, set)):
            iterable = value
        else:
            iterable = [value]
        for item in iterable:
            cleaned = _normalize_key_token(item)
            if cleaned:
                result.add(cleaned)
        return result

    def _manual_key_set() -> Set[str]:
        manual = _collect_keys_from(state.get("manual_keys"))
        if manual:
            return manual
        return _collect_keys_from(state.get("pending_keys"))

    def _pending_key_set() -> Set[str]:
        return _collect_keys_from(state.get("pending_keys"))

    def _changed_key_set() -> Set[str]:
        changed: Set[str] = set()
        for pair in state.get("changed_pairs") or []:
            reference = pair
            if "->" in reference:
                reference = reference.split("->", 1)[0]
            cleaned = _normalize_key_token(reference)
            if cleaned:
                changed.add(cleaned)
        return changed

    def _build_key_summary() -> Tuple[str, List[str], List[str]]:
        manual = _manual_key_set()
        changed = _changed_key_set()
        pending = _pending_key_set()
        derived_pending = set(pending)
        if manual:
            derived_pending.update(manual - changed)
        summary_text = f"Claves cambiadas: {len(changed)}"
        return summary_text, sorted(changed), sorted(derived_pending)

    def _pi_value_line(emp: str, tag: str) -> str:
        tag_clean = tag.strip()
        if not tag_clean:
            return ""
        rows = (state.get("pi_snapshot_map") or {}).get(emp, [])
        tag_upper = tag_clean.upper()
        for row in rows or []:
            name = str(row.get("Name") or "").strip()
            if name.upper() == tag_upper:
                value = row.get("Value")
                value_txt = str(value) if value not in (None, "") else "OK"
                return f"{tag_clean} = {value_txt}"
        missing = {t.upper() for t in (state.get("pi_missing_map") or {}).get(emp, []) or []}
        if tag_upper in missing:
            return f"{tag_clean} = No Data"
        return f"{tag_clean} = Sin lectura PI"

    def _build_company_pi_lines(emp: str) -> List[str]:
        tags = sorted((state.get("pi_tags") or {}).get(emp, []))
        if not tags:
            return []
        lines: List[str] = []
        for tag in tags:
            line = _pi_value_line(emp, tag)
            if line:
                lines.append(line)
        return lines

    def _collect_output_files(include_delete: bool = True) -> List[str]:
        paths: List[str] = []
        for key in ("report_paths", "info_paths", "query_paths"):
            paths.extend(state.get(key) or [])
        if include_delete:
            paths.extend(state.get("delete_files") or [])
            paths.extend(state.get("purge_files") or [])
        log_file = state.get("log_path")
        if log_file:
            paths.append(log_file)
        unique: List[str] = []
        for path in paths:
            if path and path not in unique:
                unique.append(path)
        return unique


    def _compose_failure_details() -> List[str]:
        lines: List[str] = []
        errors = list(dict.fromkeys(state.get("script_errors") or []))
        if errors:
            lines.append("Errores reportados durante la ejecucion:")
            lines.extend(f"  - {err}" for err in errors)
        pending = sorted(state.get("pending_keys") or [])
        if pending:
            lines.append("Keys aun presentes en groups:")
            lines.extend(f"  - {key}" for key in pending)
        scada_pend = list(dict.fromkeys(state.get("scada_pending") or []))
        if scada_pend:
            lines.append("Bits SCADA detectados como activos:")
            lines.extend(f"  - {desc}" for desc in scada_pend)
        pi_missing = list(dict.fromkeys(state.get("pi_missing") or []))
        if pi_missing:
            lines.append("Tags PI sin informacion:")
            lines.extend(f"  - {desc}" for desc in pi_missing)
        return lines

    def _fail(message: str, details: Optional[List[str]] = None):
        _console(f"[ERROR] {message}", "error")
        extra_lines = details if details is not None else _compose_failure_details()
        for line in extra_lines:
            _console(line, "error")
        _set_status(message, kind="error")
        _ui(lambda: app.stop_status())
        _restore_buttons()
        summary_text, changed_list, pending_list = _build_key_summary()
        detail_payload: List[str] = []
        detail_payload.extend(extra_lines)
        if changed_list:
            detail_payload.append("Claves modificadas:")
            for pair in changed_list:
                detail_payload.append(f"  - {pair}")
        pi_section = False
        for emp in sorted((state.get("pi_tags") or {}).keys()):
            pi_lines = _build_company_pi_lines(emp)
            if not pi_lines:
                continue
            pi_section = True
            detail_payload.append(f"{emp}:")
            for line in pi_lines:
                detail_payload.append(f"  - {line}")
        if not pi_section:
            detail_payload.append("Valores en PI: sin lecturas registradas.")
        attachments = _collect_output_files(include_delete=True)
        show_summary_dialog(
            parent=ventana,
            mensaje=summary_text or message,
            title="Cambio de SCADA Key con errores",
            status="error",
            details=detail_payload or None,
            files=attachments or None,
            show_open_file=bool(attachments),
        )

    def _finish_ok(msg: str, files: Optional[List[str]] = None):
        _restore_buttons()
        _set_status("Cambio de SCADA Key completado.", kind="success")
        _ui(lambda: app.stop_status())
        if hasattr(app, "refresh_last_upd_hsh_cambiar"):
            _ui(lambda: app.refresh_last_upd_hsh_cambiar())

        summary_text, changed_list, pending_list = _build_key_summary()
        changed_pairs = list(dict.fromkeys(state.get("changed_pairs") or []))

        # Modo validar: no hacer ver como si se hubiera aplicado el cambio
        if not state.get("apply"):
            if changed_pairs:
                resumen = "Cambios listos para hacer:\n" + "\n".join(f"  - {par}" for par in changed_pairs)
            else:
                resumen = "No se detectaron cambios listos para aplicar."
            attachments = _collect_output_files(include_delete=False)
            for extra in files or []:
                if extra and extra not in attachments:
                    attachments.append(extra)
            show_summary_dialog(
                parent=ventana,
                mensaje=resumen,
                title="Validacion Cambio de SCADA Key lista",
                status="success",
                details=None,
                files=attachments or None,
                show_open_file=bool(attachments),
            )
            return

        pi_reports = state.get("pi_reports", [])
        pi_missing = state.get("pi_missing", [])

        final_lines: List[str] = []
        if msg:
            final_lines.extend([line for line in msg.splitlines() if line.strip()])

        detail_payload: List[str] = []
        if changed_pairs:
            detail_payload.append("Claves modificadas:")
            for pair in changed_pairs:
                detail_payload.append(f"  - {pair}")
        pi_sections_added = False
        for emp in sorted((state.get("pi_tags") or {}).keys()):
            pi_lines = _build_company_pi_lines(emp)
            if not pi_lines:
                continue
            pi_sections_added = True
            detail_payload.append(f"{emp}:")
            for line in pi_lines:
                detail_payload.append(f"  - {line}")
        if not pi_sections_added:
            detail_payload.append("Valores en PI: sin lecturas registradas.")
        attachments = _collect_output_files(include_delete=True)
        for extra in files or []:
            if extra and extra not in attachments:
                attachments.append(extra)

        show_summary_dialog(
            parent=ventana,
            mensaje=summary_text or "Proceso completado.",
            title="Cambio de SCADA Key completado",
            status="success",
            details=detail_payload or None,
            files=attachments or None,
            show_open_file=bool(attachments),
        )

        # Al completar correctamente en modo aplicar, habilitar la consulta PI dedicada
        if state.get("apply"):
            try:
                setattr(app, "cambiar_key_ready_for_pi", True)
                boton_pi = getattr(app, "boton_consultar_pi_cambiar", None)
                if boton_pi is not None:
                    boton_pi.config(state="normal")
            except Exception:
                pass

    def _on_progress_factory(tag: str):
        def _handler(line: str):
            text = (line or "").strip()
            if not text:
                return
            lower = text.lower()
            level = "info"
            if "error" in lower or "traceback" in lower or "exception" in lower:
                level = "error"
            elif "warn" in lower or "warning" in lower:
                level = "warn"
            _console(f"[{tag}] {text}", level)
        return _handler

    def _parse_script_line(raw_line: str):
        line = (raw_line or "").strip()
        if not line:
            return

        # Sistema de estado mejorado
        if line.startswith("APPLY_OK:"):
            try:
                _, payload = line.split("APPLY_OK:", 1)
                emp_part, detail = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                state.setdefault("verification_status", {}).setdefault(emp_key, {}).setdefault("aplicacion", []).append(detail)
                _console(f"[APLICADO] {emp_key}: {detail}", "info")
            except ValueError:
                pass

        elif line.startswith("APPLY_SERVER:"):
            try:
                _, payload = line.split("APPLY_SERVER:", 1)
                emp_part, server_part = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                server_used = server_part.strip()
                state["applied_servers"][emp_key] = server_used
                _console(f"[SERVIDOR] {emp_key} usando: {server_used}", "info")
            except ValueError:
                pass

        elif line.startswith("VERIFICATION_STATUS:"):
            try:
                _, payload = line.split("VERIFICATION_STATUS:", 1)
                emp_part, status_detail = payload.split(":", 1)
                emp_key = emp_part.strip().upper()
                state.setdefault("verification_status", {}).setdefault(emp_key, {}).setdefault("verificacion", []).append(status_detail)
                _console(f"[VERIFICACION] {emp_key}: {status_detail}", "info")
            except ValueError:
                pass

        elif line.startswith("MONGO_SUMMARY:"):
            mensaje = line.split(":", 1)[1].strip()
            state["mongo_summary"].append(mensaje)
            _console(f"[MONGO] {mensaje}", "info")

        elif line.startswith("SCADA_DISABLE:"):
            detalle = line.split(":", 1)[1].strip()
            state["scada_disable"].append(detalle)
            _console(f"[SCADA-OFF] {detalle}", "info")

        elif line.startswith("SCADA_ENABLE:"):
            detalle = line.split(":", 1)[1].strip()
            state["scada_enable"].append(detalle)
            _console(f"[SCADA-ON] {detalle}", "info")

        elif line.startswith("SCADA_STILL_ON:"):
            detalle = line.split(":", 1)[1].strip()
            state.setdefault("scada_pending", []).append(detalle)
            _console(f"[SCADA-PENDIENTE] {detalle}", "warn")

        elif line.startswith("PI_REPORT:"):
            detalle = line.split(":", 1)[1].strip()
            state["pi_reports"].append(detalle)
            _console(f"[PI] {detalle}", "info")

        elif line.startswith("PI_MISSING:"):
            detalle = line.split(":", 1)[1].strip()
            state["pi_missing"].append(detalle)
            _console(f"[PI-MISSING] {detalle}", "warn")

        elif line.startswith("PI_TAG:"):
            detalle = line.split(":", 1)[1].strip()
            if detalle:
                try:
                    emp_part, tag_part = detalle.split("|", 1)
                    emp_key = emp_part.strip().upper()
                    tag_value = tag_part.strip()
                    if tag_value:
                        state.setdefault("pi_tags", {}).setdefault(emp_key, set()).add(tag_value)
                        _console(f"[PI-TAG] {emp_key}: {tag_value}", "info")
                except ValueError:
                    pass

        # Paths y archivos
        elif line.startswith("REPORT_PATH:"):
            path = line.split(":", 1)[1].strip()
            if path:
                state["report_paths"].append(path)
                _console(f"[REPORT] {path}", "info")
        elif line.startswith("INFO_PATH:"):
            path = line.split(":", 1)[1].strip()
            if path:
                state["info_paths"].append(path)
                _console(f"[INFO] {path}", "info")
        elif line.startswith("QUERY_PATH:"):
            path = line.split(":", 1)[1].strip()
            if path:
                state["query_paths"].append(path)
                _console(f"[QUERY] {path}", "info")
        elif line.startswith("DELETE_FILE:"):
            path = line.split(":", 1)[1].strip()
            if path:
                state["delete_files"].append(path)
                _console(f"[DELETE] {path}", "warn")
        elif line.startswith("PURGE_FILE:"):
            path = line.split(":", 1)[1].strip()
            if path:
                state["purge_files"].append(path)
                _console(f"[PURGE] {path}", "warn")

        elif line.startswith("PENDING_KEY:"):
            key = line.split(":", 1)[1].strip().upper()
            if key:
                state["pending_keys"].add(key)
                _console(f"[PENDIENTE] {key}", "warn")

        elif line.startswith("MESSAGE:"):
            mensaje = line.split(":", 1)[1].strip()
            state["script_messages"].append(mensaje)
            if mensaje.startswith("Procesando par"):
                try:
                    contenido = mensaje.split("Procesando par", 1)[1]
                    old_part, new_part = contenido.split("->", 1)
                    old_key = old_part.strip().strip(":")
                    new_key = new_part.strip()
                    if old_key and new_key:
                        state.setdefault("changed_pairs", []).append(f"{old_key} -> {new_key}")
                except Exception:
                    pass

        elif line.startswith("ERROR:"):
            detalle = line.split(":", 1)[1].strip()
            if detalle:
                state.setdefault("script_errors", []).append(detalle)
            _console(f"[SCRIPT-ERROR] {detalle}", "error")

        else:
            _console(f"[SCRIPT] {line}", "info")

    def _on_script_progress(line: str):
        _parse_script_line(line)

    def _scada_toggle_guaranteed(actions: List[str], enable: bool) -> Tuple[List[str], bool]:
        """Ejecuta operaciones SCADA  con verificacion en TODOS los dominios"""
        if not actions:
            return [], False

        resumen: List[str] = []
        fallos = False
        env_secure = app.secure_env()
        prev_env = {k: os.environ.get(k) for k in env_secure}
        os.environ.update(env_secure)

        logger_obj = logger_main
        logger_console_obj = logger_console_main
        if Logger is not None and (logger_obj is None or logger_console_obj is None):
            try:
                log_file = log_dir / ("hsh_cambiar_key_scada_on.log" if enable else "hsh_cambiar_key_scada_off.log")
                logger_obj, logger_console_obj = Logger.initlog(str(log_file), append=True)
            except Exception:
                logger_obj = logger_console_obj = None

        def _log(level: str, mensaje: str):
            _console(f"[SCADA] {mensaje}", "info" if level == "info" else "error")
            if Logger is not None and logger_obj is not None and logger_console_obj is not None:
                try:
                    Logger.write_log().log_all(level, mensaje, logger_console_obj, logger_obj)
                except Exception:
                    pass

        # Agrupar acciones por empresa para tracking
        acciones_por_empresa = {}
        for descriptor in actions:
            parts = [p.strip() for p in descriptor.split("|")]
            if len(parts) < 4:
                resumen.append(f"Formato SCADA invalido: {descriptor}")
                fallos = True
                continue

            empresa_scada, dominio_scada, base_key, bit_spec = parts[:4]
            if empresa_scada not in acciones_por_empresa:
                acciones_por_empresa[empresa_scada] = []
            acciones_por_empresa[empresa_scada].append(descriptor)

        # Ejecutar por empresa con tracking
        for empresa_scada, descriptors in acciones_por_empresa.items():
            _log("info", f"Procesando {len(descriptors)} acciones SCADA para {empresa_scada}")

            for descriptor in descriptors:
                parts = [p.strip() for p in descriptor.split("|")]
                empresa_scada, dominio_scada, base_key, bit_spec = parts[:4]
                empresa_upper = empresa_scada.upper()

                hosts_to_try: List[str] = []
                if enable:
                    hosts_to_try = [h for h in SCADA_HOSTS_FULL.get(empresa_upper, []) if h]

                host_default = app.generar_server(empresa_scada, dominio_scada)
                if not hosts_to_try and host_default:
                    hosts_to_try = [host_default]

                if not hosts_to_try:
                    mensaje = f"No se pudo resolver host SCADA para {empresa_scada} dominio {dominio_scada}"
                    _log("error", mensaje)
                    resumen.append(mensaje)
                    fallos = True
                    continue

                for host in hosts_to_try:
                    current_domain = dominio_scada if not enable else ("QA" if "qds" in host.lower() else "CC")
                    client = None
                    try:
                        accion = "encender" if enable else "apagar"
                        _log("info", f"Conectando a {host} para {accion} {base_key} ({bit_spec})")
                        if Logger is not None and logger_obj is not None and logger_console_obj is not None:
                            client = sshserver(host, logger_obj, logger_console_obj)
                        else:
                            temp_logger = temp_logger_console = None
                            if Logger is not None:
                                try:
                                    temp_logger, temp_logger_console = Logger.initlog(str(log_dir / "hsh_cambiar_key_scada_tmp.log"), append=True)
                                except Exception:
                                    temp_logger = temp_logger_console = None
                            if temp_logger is not None and temp_logger_console is not None:
                                logger_obj = temp_logger
                                logger_console_obj = temp_logger_console
                            target_logger = logger_obj
                            target_console = logger_console_obj
                            if target_logger is None or target_console is None:
                                raise RuntimeError("No se pudo inicializar logger para sshserver")
                            client = sshserver(host, target_logger, target_console)
                        if client is None:
                            raise RuntimeError("sshserver devolvio None")

                        host_online = None
                        if scada_online is not None:
                            try:
                                host_online = scada_online(client, logger_obj, logger_console_obj)
                            except Exception as exc:
                                _log("warn", f"{host}: error verificando estado ONLINE ({exc})")
                        if scada_online is not None and not host_online:
                            msg = f"SCADA {host}: sin estado ONLINE, se omite {accion} {base_key}."
                            resumen.append(msg)
                            _log("warn", msg)
                            fallos = True
                            state.setdefault("verification_status", {}).setdefault(
                                empresa_upper, {}
                            ).setdefault("scada", []).append(msg)
                            continue
                        if host_online:
                            _log("info", f"{host}: estado ONLINE detectado ({host_online}).")

                        parts_spec = bit_spec.split(":")
                        if len(parts_spec) != 2:
                            raise ValueError(f"Bit spec invalido: {bit_spec}")

                        tipo = int(parts_spec[0])
                        bit = int(parts_spec[1])
                        valor = 1 if enable else 0
                        cmd = f". ~/.bash_profile && dbset -k 10 {tipo} 12 {base_key} {bit} = {valor}"
                        _log("info", f"Ejecutando: {cmd}")

                        stdin, stdout, stderr = client.exec_command(cmd)
                        rc = stdout.channel.recv_exit_status()

                        if rc == 0:
                            msg = f"{'Encendido' if enable else 'Apagado'} OK {empresa_scada} {current_domain} {base_key} bit {bit}"
                            resumen.append(msg)
                            _log("info", msg)
                            state.setdefault("verification_status", {}).setdefault(empresa_upper, {}).setdefault(
                                "scada", []
                            ).append(msg)

                            if enable:
                                if empresa_scada == state["empresa"]:
                                    state["scada_actions_completed"]["enable_principal"] = True
                                elif empresa_scada == state["respaldo"]:
                                    state["scada_actions_completed"]["enable_respaldo"] = True
                            else:
                                if empresa_scada == state["empresa"]:
                                    state["scada_actions_completed"]["disable_principal"] = True
                                elif empresa_scada == state["respaldo"]:
                                    state["scada_actions_completed"]["disable_respaldo"] = True

                        else:
                            err = stderr.read().decode("utf-8", "ignore").strip()
                            msg = f"Fallo SCADA {empresa_scada} {current_domain} {base_key} bit {bit} (rc={rc}) {err}"
                            resumen.append(msg)
                            _log("error", msg)
                            fallos = True

                    except Exception as exc:
                        fallos = True
                        resumen.append(f"Error {host}: {exc}")
                        _log("error", f"Error {host}: {exc}")
                    finally:
                        try:
                            if client:
                                client.close()
                        except Exception:
                            pass

        for key, prev in prev_env.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev

        return resumen, fallos

    def _prompt_delete_confirmation(files: List[str]) -> None:
        """Dialogo de confirmacion mejorado con informacion de estado """
        parent = ventana
        if not parent:
            proceed = messagebox.askyesno(
                "Confirmar eliminacion",
                "Confirma que ejecutaste los archivos Delete/Purge y eliminaste las claves en grupos?",
            )
            if proceed:
                _trigger_cleanup_pipeline_guaranteed()  #  CORREGIDO: usar funcion correcta
            else:
                _fail("Debes completar la eliminacion manual para continuar.")
            return

        win = tk.Toplevel(parent)
        make_modal(
            win,
            "Confirmar eliminacion HSH - bits ya apagados",
            width=700,
            height=400,
            parent=parent,
            modal=True,
            use_transient=True,
            resizable=True,
        )
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        container = tk.Frame(win)
        container.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        # Informacion de estado
        pendientes_keys = sorted(set(state.get("pending_keys", set())) or state.get("manual_keys", []))
        info_lines = [
            " : Los bits de envio para las keys actuales YA FUERON APAGADOS",
            "   en TODOS los dominios (CC y QA) para AMBAS empresas.",
            "",
            "ARCHIVOS GENERADOS PARA ELIMINACION:",
            " Delete: elimina los registros en groups.",
            " Purge: realiza limpieza profunda de la clave.",
            "",
            "Pasos REQUERIDOS:",
            "1. Ejecuta TODOS los archivos Delete/Purge en el servidor HSH.",
            "2. Verifica que las claves ya no aparezcan en groups.",
            "3. Confirma aqui cuando hayas terminado.",
        ]
        if pendientes_keys:
            info_lines.append("")
            info_lines.append(f"Claves a eliminar: {', '.join(pendientes_keys)}")
        info_text = "\n".join(info_lines)

        tk.Label(
            container,
            text=info_text,
            justify="left",
            anchor="w",
            font=("TkDefaultFont", 9)
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        listbox = tk.Listbox(container, height=10, activestyle="dotbox", font=("TkDefaultFont", 9))
        listbox.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        scrollbar = tk.Scrollbar(container, orient="vertical", command=listbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 12))
        listbox.configure(yscrollcommand=scrollbar.set)

        for idx, item in enumerate(files):
            listbox.insert(idx, item)

        def _selected_path() -> Optional[str]:
            try:
                sel = listbox.curselection()
                if not sel:
                    return files[0] if files else None
                return files[sel[0]]
            except Exception:
                return None

        buttons = tk.Frame(container)
        buttons.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        buttons.columnconfigure(2, weight=1)
        buttons.columnconfigure(3, weight=1)

        def _open_selected():
            path = _selected_path()
            if path and not open_path(path):
                messagebox.showerror("Error", "No se pudo abrir el archivo.", parent=win)

        def _reveal_selected():
            path = _selected_path()
            if not path:
                return
            ok = open_in_file_manager(path, select=not os.path.isdir(path))
            if not ok:
                messagebox.showerror("Error", "No se pudo mostrar en el explorador.", parent=win)

        def _copy_selected():
            path = _selected_path()
            if not path:
                return
            try:
                win.clipboard_clear()
                win.clipboard_append(path)
                messagebox.showinfo("Copiado", "Ruta copiada al portapapeles.", parent=win)
            except Exception:
                pass

        tk.Button(buttons, text="Abrir", command=_open_selected).grid(row=0, column=0, padx=4)
        tk.Button(buttons, text="Mostrar en carpeta", command=_reveal_selected).grid(row=0, column=1, padx=4)
        tk.Button(buttons, text="Copiar ruta", command=_copy_selected).grid(row=0, column=2, padx=4)

        confirmed = {"value": False}

        def _confirm():
            confirmed["value"] = True
            win.destroy()

        def _cancel():
            confirmed["value"] = False
            win.destroy()

        tk.Button(buttons, text=" Confirmar eliminacion", command=_confirm,
                 fg="#0a0", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=3, padx=4)

        footer = tk.Frame(container)
        footer.grid(row=3, column=0, columnspan=2, sticky="e")
        tk.Button(footer, text="Cancelar", command=_cancel).grid(row=0, column=0)

        win.protocol("WM_DELETE_WINDOW", lambda: None)
        win.wait_window()

        if confirmed["value"]:
            _console(" Usuario confirmo la ejecucion de archivos Delete/Purge.", "info")
            _trigger_cleanup_pipeline_guaranteed()  #  CORREGIDO: usar funcion correcta
        else:
            _fail("El usuario cancelo la confirmacion de eliminacion.")

    run_targets: List[Dict[str, object]] = [
        {
            "empresa": empresa,
            "server": servidor_principal,
            "skip_backup": True,
        }
    ]
    if respaldo:
        run_targets.append(
            {
                "empresa": respaldo,
                "server": servidor_respaldo,
                "skip_backup": True,
            }
        )
    state["run_targets"] = run_targets

    def _new_aggregate_state() -> Dict[str, object]:
        return {
            "report_paths": [],
            "info_paths": [],
            "query_paths": [],
            "delete_files": [],
            "purge_files": [],
            "mongo_summary": [],
            "script_messages": [],
            "changed_pairs": [],
            "scada_disable": [],
            "scada_enable": [],
            "scada_pending": [],
            "pending_keys": set(),
            "manual_keys": set(),
            "pi_tags": {},
            "pi_reports": [],
            "pi_missing": [],
            "script_errors": [],
            "pi_snapshot_map": {},
            "pi_missing_map": {},
            "pi_snapshot_messages": [],
            "pi_snapshot_collected_at": None,
            "applied_servers": {},
            "verification_status": {},
            "scada_actions_completed": {
                "disable_principal": False,
                "disable_respaldo": False,
                "enable_principal": False,
                "enable_respaldo": False,
            },
        }

    def _prepare_state_for_run():
        state["report_paths"] = []
        state["info_paths"] = []
        state["query_paths"] = []
        state["delete_files"] = []
        state["purge_files"] = []
        state["mongo_summary"] = []
        state["script_messages"] = []
        state["changed_pairs"] = []
        state["scada_disable"] = []
        state["scada_enable"] = []
        state["scada_pending"] = []
        state["pending_keys"] = set()
        state["manual_keys"] = set()
        state["pi_tags"] = {}
        state["pi_reports"] = []
        state["pi_missing"] = []
        state["script_errors"] = []
        state["pi_snapshot_map"] = {}
        state["pi_missing_map"] = {}
        state["pi_snapshot_messages"] = []
        state["pi_snapshot_collected_at"] = None
        state["applied_servers"] = {}
        state["verification_status"] = {}
        state["scada_actions_completed"] = {
            "disable_principal": False,
            "disable_respaldo": False,
            "enable_principal": False,
            "enable_respaldo": False,
        }
        state["report_excel_path"] = None

    def _merge_current_results(aggregate: Dict[str, object]) -> None:
        def _extend_list(key: str) -> None:
            aggregate[key].extend(state.get(key) or [])

        for list_key in (
            "report_paths",
            "info_paths",
            "query_paths",
            "delete_files",
            "purge_files",
            "mongo_summary",
            "script_messages",
            "changed_pairs",
            "scada_disable",
            "scada_enable",
            "scada_pending",
            "pi_reports",
            "pi_missing",
            "script_errors",
            "pi_snapshot_messages",
        ):
            _extend_list(list_key)

        aggregate["pending_keys"].update(state.get("pending_keys") or [])
        current_manual = state.get("manual_keys") or set()
        if isinstance(current_manual, set):
            aggregate["manual_keys"].update(current_manual)
        elif isinstance(current_manual, (list, tuple)):
            aggregate["manual_keys"].update(current_manual)
        elif current_manual:
            aggregate["manual_keys"].add(current_manual)

        for emp, tags in (state.get("pi_tags") or {}).items():
            agg_set = aggregate["pi_tags"].setdefault(emp, set())
            agg_set.update(tags)

        for emp, rows in (state.get("pi_snapshot_map") or {}).items():
            if not rows:
                continue
            agg_rows = aggregate["pi_snapshot_map"].setdefault(emp, [])
            agg_rows.extend(rows)

        for emp, missing_tags in (state.get("pi_missing_map") or {}).items():
            if not missing_tags:
                continue
            agg_missing = aggregate["pi_missing_map"].setdefault(emp, set())
            agg_missing.update(missing_tags)

        for emp, server_used in (state.get("applied_servers") or {}).items():
            aggregate["applied_servers"][emp] = server_used

        for emp, data in (state.get("verification_status") or {}).items():
            aggregate["verification_status"].setdefault(emp, {}).update(data)

        current_actions = state.get("scada_actions_completed") or {}
        for key, value in current_actions.items():
            if value:
                aggregate["scada_actions_completed"][key] = True

        collected_at = state.get("pi_snapshot_collected_at")
        if collected_at:
            aggregate["pi_snapshot_collected_at"] = collected_at

    def _apply_aggregate_to_state(aggregate: Dict[str, object]) -> None:
        def _unique_list(values: List[str]) -> List[str]:
            return list(dict.fromkeys(values))

        for list_key in (
            "report_paths",
            "info_paths",
            "query_paths",
            "delete_files",
            "purge_files",
            "mongo_summary",
            "script_messages",
            "changed_pairs",
            "scada_disable",
            "scada_enable",
            "scada_pending",
            "pi_reports",
            "pi_missing",
            "script_errors",
            "pi_snapshot_messages",
        ):
            state[list_key] = _unique_list(aggregate[list_key])

        state["pending_keys"] = set(aggregate["pending_keys"])
        state["manual_keys"] = sorted(aggregate["manual_keys"])
        state["pi_tags"] = {emp: set(tags) for emp, tags in aggregate["pi_tags"].items()}
        state["pi_snapshot_map"] = {emp: list(rows) for emp, rows in aggregate["pi_snapshot_map"].items()}
        state["pi_missing_map"] = {emp: sorted(missing) for emp, missing in aggregate["pi_missing_map"].items()}
        state["applied_servers"] = dict(aggregate["applied_servers"])
        state["verification_status"] = {emp: dict(data) for emp, data in aggregate["verification_status"].items()}
        state["scada_actions_completed"] = dict(aggregate["scada_actions_completed"])
        state["pi_snapshot_collected_at"] = aggregate.get("pi_snapshot_collected_at")
        state["script_errors"] = _unique_list(aggregate.get("script_errors", []))

    def _run_script_guaranteed(check_only: bool):
        """Ejecuta el script de Cambiar Key para cada empresa de forma secuencial."""
        run_targets_queue = [dict(target) for target in state.get("run_targets") or []]
        if not run_targets_queue:
            _fail("No hay empresas configuradas para ejecutar el cambio de key.")
            return

        previous_delete_files: List[str] = []
        previous_purge_files: List[str] = []
        previous_scada_enable: List[str] = []
        previous_changed_pairs: List[str] = []
        previous_pi_tags: Dict[str, Set[str]] = {}
        previous_applied_servers: Dict[str, str] = {}
        if check_only:
            previous_delete_files = list(dict.fromkeys(state.get("delete_files") or []))
            previous_purge_files = list(dict.fromkeys(state.get("purge_files") or []))
            previous_scada_enable = list(dict.fromkeys(state.get("scada_enable") or []))
            previous_changed_pairs = list(dict.fromkeys(state.get("changed_pairs") or []))
            previous_pi_tags = {emp: set(tags) for emp, tags in (state.get("pi_tags") or {}).items() if tags}
            previous_applied_servers = dict(state.get("applied_servers") or {})

        aggregate = _new_aggregate_state()
        if previous_delete_files:
            aggregate["delete_files"].extend(previous_delete_files)
        if previous_purge_files:
            aggregate["purge_files"].extend(previous_purge_files)
        if previous_scada_enable:
            aggregate["scada_enable"].extend(previous_scada_enable)
        if previous_changed_pairs:
            aggregate["changed_pairs"].extend(previous_changed_pairs)
        if previous_pi_tags:
            for emp, tags in previous_pi_tags.items():
                aggregate["pi_tags"].setdefault(emp, set()).update(tags)
        if previous_applied_servers:
            aggregate["applied_servers"].update(previous_applied_servers)
        state["_aggregate"] = aggregate

        def _run_next():
            if not run_targets_queue:
                _apply_aggregate_to_state(aggregate)
                _after_all_scripts(check_only)
                return

            target = run_targets_queue.pop(0)
            _prepare_state_for_run()

            empresa_target = target.get("empresa")
            server_target = target.get("server")
            skip_backup_flag = bool(target.get("skip_backup", False))
            label = str(empresa_target or "?")

            if check_only:
                _set_status(f"Verificando limpieza en HSH ({label})...")
            else:
                _set_status(f"Ejecutando validaciones  ({label})...")

            cmd = build_cmd("scripts.hsh_cambiar_key", label, "--input", state["excel"])
            if state["apply"] and not check_only:
                cmd.append("--apply")
            if check_only:
                cmd.append("--check-only")
            if server_target:
                cmd += ["--server", server_target]
            if skip_backup_flag:
                cmd.append("--skip-backup")
            else:
                respaldo_cli = target.get("respaldo")
                if respaldo_cli:
                    cmd += ["--respaldo", respaldo_cli]
                    server_respaldo = target.get("server_respaldo")
                    if server_respaldo:
                        cmd += ["--server-respaldo", server_respaldo]

            _console(f">> CMD[CAMBIAR_KEY:{label}]: {' '.join(map(str, cmd))}", "warn")
            app.tasks.run_subprocess(
                cmd,
                env=env,
                cwd=cwd,
                on_progress=_on_script_progress,
                on_done=lambda rc, tgt=target: _after_single_run(rc, tgt),
            )

        def _after_single_run(rc: int, target_info: Dict[str, object]):
            if rc != 0:
                nombre = target_info.get("empresa") or "?"
                detalles = _compose_failure_details()
                _fail(f"El proceso para {nombre} termino con errores.", detalles if detalles else None)
                return
            _merge_current_results(aggregate)
            _run_next()

        _run_next()

    def _after_all_scripts(check_only: bool):
        """Procesa los resultados agregados tras ejecutar todas las empresas."""
        if not state["apply"]:
            resumen: List[str] = []
            if state["mongo_summary"]:
                resumen.extend(state["mongo_summary"])

            pares = list(dict.fromkeys(state.get("changed_pairs") or []))
            if pares:
                if resumen:
                    resumen.append("")
                resumen.append("Claves detectadas:")
                for par in pares:
                    resumen.append(f"  - {par}")

            msg = "\n".join(resumen) if resumen else "Validacion completada. Revisa los reportes generados."
            _generate_report_excel()
            files = list(dict.fromkeys(state["report_paths"] + state["info_paths"] + state["query_paths"]))
            _finish_ok(msg, files=files)
            return

        if check_only:
            pendientes = state.get("pending_keys") or set()
            scada_pend = list(state.get("scada_pending") or [])
            if scada_pend:
                _console(" Se detectaron bits activos tras la limpieza. Intentando apagarlos automaticamente...", "warn")
                resumen_auto, fallos_auto = _scada_toggle_guaranteed(scada_pend, enable=False)
                for linea in resumen_auto:
                    _console(f"[SCADA-AUTO] {linea}", "info")
                if not fallos_auto:
                    scada_pend = []
                    state["scada_pending"] = []
                    _console(" Bits SCADA apagados automáticamente. Continuando con la verificación.", "info")
                else:
                    _console(" No fue posible apagar todos los bits automaticamente.", "error")
            if pendientes or scada_pend:
                message_lines = []
                if pendientes:
                    claves = ", ".join(sorted(pendientes))
                    message_lines.append("Se detectaron claves que aun existen en groups despues de la eliminacion manual.")
                    message_lines.append(f"Claves pendientes: {claves}")
                if scada_pend:
                    message_lines.append("")
                    message_lines.append("Se encontraron bits activos en SCADA que deben apagarse antes de continuar:")
                    for descriptor in scada_pend:
                        message_lines.append(f" - {descriptor}")
                message_lines.append("")
                message_lines.append("Ejecuta nuevamente los archivos Delete/Purge y vuelve a confirmar.")
                messagebox.showwarning("Pendientes en verificacion", "\n".join(message_lines), parent=ventana)
                _prompt_delete_confirmation(state["delete_files"] + state["purge_files"])
                return

            _console(" Verificacion de limpieza completada (groups y SCADA).", "info")
            _run_scada_enable_guaranteed_and_pi()
            return

        if state.get("scada_disable"):
            _set_status(" Apagando bits de las keys actuales...", indeterminate=True)
            _console(" Apagando bits de las keys actuales en todos los dominios...", "warn")
            resumen_off, fallos_off = _scada_toggle_guaranteed(state["scada_disable"], enable=False)
            for linea in resumen_off:
                _console(f"[SCADA-OFF] {linea}", "info")
            if fallos_off:
                _fail("No fue posible apagar todos los bits de envio en SCADA. Revisa la consola.")
                return
            state["bits_apagados"] = True
            state["scada_disable"] = []
            _console(" Bits apagados. Las keys anteriores no deberian regenerarse en groups.", "info")

        manual_keys_sorted = sorted(state.get("pending_keys") or [])
        state["manual_keys"] = manual_keys_sorted
        archivos = list(dict.fromkeys(state["delete_files"] + state["purge_files"]))
        if archivos:
            _console(f" Archivos Delete/Purge generados ({len(archivos)}):", "info")
            for archivo in archivos:
                _console(f" - {archivo}", "info")
            _set_status("Esperando confirmacion de eliminacion manual en HSH...")
            _prompt_delete_confirmation(archivos)
        else:
            _console(" No se generaron archivos Delete/Purge. Continuando con verificacion.", "warn")
            _trigger_cleanup_pipeline_guaranteed()

    def _run_scada_enable_guaranteed_and_pi():
        """Fase final : encender bits de keys nuevas y (opcionalmente) consultar PI basado en TAGS"""
        _set_status(" Encendiendo bits para las keys nuevas...", indeterminate=True)
        _console(" Encendiendo bits para las keys nuevas en todos los dominios...", "warn")
        resumen_on, fallos_on = _scada_toggle_guaranteed(state["scada_enable"], enable=True)
        for linea in resumen_on:
            _console(f"[SCADA-ON] {linea}", "info")

        if fallos_on:
            _fail("Algunos bits SCADA no pudieron encenderse. Revisa la consola para mas detalles.")
            return

        def _finalize_guaranteed(resumen_bits: List[str]):
            final_lines: List[str] = []
            if state["mongo_summary"]:
                final_lines.extend(state["mongo_summary"])

            changed = list(dict.fromkeys(state.get("changed_pairs") or []))
            if changed:
                if final_lines:
                    final_lines.append("")
                final_lines.append("Claves modificadas:")
                for par in changed:
                    final_lines.append(f"  - {par}")

            if resumen_bits:
                if final_lines:
                    final_lines.append("")
                final_lines.append("Bits encendidos:")
                final_lines.extend(resumen_bits)

            if state["pi_reports"]:
                if final_lines:
                    final_lines.append("")
                final_lines.append("Resultados PI:")
                final_lines.extend(state["pi_reports"])

            if state["pi_missing"]:
                if final_lines:
                    final_lines.append("")
                final_lines.append("PI sin datos:")
                final_lines.extend(state["pi_missing"])

            if not final_lines:
                final_lines.append("Proceso completado correctamente.")

            msg = "\n".join(final_lines)
            _generate_report_excel()
            files = list(dict.fromkeys(state["report_paths"] + state["info_paths"] + state["delete_files"] + state["purge_files"]))
            _finish_ok(msg, files=files)

        # La consulta a PI se ejecuta solo desde un boton dedicado.
        # Aqui simplemente finalizamos el flujo principal usando el resumen de bits encendidos.
        _finalize_guaranteed(resumen_on)


    def _run_pipeline_full_guaranteed():
        """Pipeline completo  con mensajes mejorados"""
        cmd_import_principal = build_cmd(
            "scripts.importar_all",
            state["servidor_principal"],
            state["empresa"],
            "sca,hsh",
            "--usecase",
            "hsh_cambiar_key",
        )
        cmd_import_respaldo = (
            build_cmd(
                "scripts.importar_all",
                state["servidor_respaldo"],
                state["respaldo"],
                "sca,hsh",
                "--usecase",
                "hsh_cambiar_key",
            )
            if state.get("respaldo") and state.get("servidor_respaldo")
            else None
        )
        cmd_conv_sca = build_cmd("scripts.Convertir_all", state["empresa"], "Validar_HSH", "--only", "sca")
        cmd_conv_hsh = build_cmd("scripts.Convertir_all", state["empresa"], "Validar_HSH", "--only", "hsh")
        cmd_conv_sca_res = (
            build_cmd("scripts.Convertir_all", state["respaldo"], "Validar_HSH", "--only", "sca")
            if state.get("respaldo")
            else None
        )
        cmd_conv_hsh_res = (
            build_cmd("scripts.Convertir_all", state["respaldo"], "Validar_HSH", "--only", "hsh")
            if state.get("respaldo")
            else None
        )

        def _run_convert_hsh_res():
            if not (state.get("respaldo") and cmd_conv_hsh_res):
                _run_script_guaranteed(check_only=False)
                return
            _set_status(f"Convirtiendo HSH respaldo {state['respaldo']}...")
            _console(f">> CMD[CONVERT HSH respaldo]: {' '.join(map(str, cmd_conv_hsh_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_hsh_res,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-HSH-RES"),
                on_done=lambda rc: (_run_script_guaranteed(False) if rc == 0 else _fail(f"Conversion HSH respaldo ({state['respaldo']}) fallo")),
            )

        def _run_convert_sca_res():
            if not (state.get("respaldo") and cmd_conv_sca_res):
                _run_convert_hsh_res()
                return
            _set_status(f"Convirtiendo SCADA respaldo {state['respaldo']}...")
            _console(f">> CMD[CONVERT SCADA respaldo]: {' '.join(map(str, cmd_conv_sca_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_sca_res,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-SCADA-RES"),
                on_done=lambda rc: (_run_convert_hsh_res() if rc == 0 else _fail(f"Conversion SCADA respaldo ({state['respaldo']}) fallo")),
            )

        def _run_convert_hsh():
            _set_status("Convirtiendo HSH principal...")
            _console(f">> CMD[CONVERT HSH principal]: {' '.join(map(str, cmd_conv_hsh))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_hsh,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-HSH"),
                on_done=lambda rc: (_run_convert_sca_res() if rc == 0 else _fail("Conversion HSH principal fallo")),
            )

        def _run_convert_sca():
            _set_status("Convirtiendo SCADA principal...")
            _console(f">> CMD[CONVERT SCADA principal]: {' '.join(map(str, cmd_conv_sca))}", "warn")
            app.tasks.run_subprocess(
                cmd_conv_sca,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-SCADA"),
                on_done=lambda rc: (_run_convert_hsh() if rc == 0 else _fail("Conversion SCADA principal fallo")),
            )

        def _after_import_res(rc: int):
            if rc != 0:
                _fail("Importacion SCADA/HSH respaldo fallo")
                return
            _run_convert_sca()

        def _run_import_res():
            if not cmd_import_respaldo:
                _run_convert_sca()
                return
            _set_status(f"Sincronizando hsh_cambiar_key respaldo ({state['respaldo']})...")
            _console(f">> CMD[IMPORT respaldo]: {' '.join(map(str, cmd_import_respaldo))}", "warn")
            app.tasks.run_subprocess(
                cmd_import_respaldo,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("IMPORT-RES"),
                on_done=_after_import_res,
            )

        def _after_import_principal(rc: int):
            if rc != 0:
                _fail("Importacion SCADA/HSH principal fallo")
                return
            _run_import_res()

        _set_status("Sincronizando hsh_cambiar_key (SCADA+HSH)...")
        _console(f">> CMD[IMPORT principal]: {' '.join(map(str, cmd_import_principal))}", "warn")
        app.tasks.run_subprocess(
            cmd_import_principal,
            env=env,
            cwd=cwd,
            on_progress=_on_progress_factory("IMPORT"),
            on_done=_after_import_principal,
        )

    def _run_pipeline_refresh_guaranteed():
        """Pipeline de actualizacion  para verificacion"""
        cmd_import_principal = build_cmd(
            "scripts.importar_all",
            state["servidor_principal"],
            state["empresa"],
            "sca,hsh",
            "--usecase",
            "hsh_cambiar_key",
        )
        cmd_import_respaldo = (
            build_cmd(
                "scripts.importar_all",
                state["servidor_respaldo"],
                state["respaldo"],
                "sca,hsh",
                "--usecase",
                "hsh_cambiar_key",
            )
            if state.get("respaldo") and state.get("servidor_respaldo")
            else None
        )
        cmd_convert_sca = build_cmd("scripts.Convertir_all", state["empresa"], "Validar_HSH", "--only", "sca")
        cmd_convert_hsh = build_cmd("scripts.Convertir_all", state["empresa"], "Validar_HSH", "--only", "hsh")
        cmd_convert_sca_res = (
            build_cmd("scripts.Convertir_all", state["respaldo"], "Validar_HSH", "--only", "sca")
            if state.get("respaldo")
            else None
        )
        cmd_convert_hsh_res = (
            build_cmd("scripts.Convertir_all", state["respaldo"], "Validar_HSH", "--only", "hsh")
            if state.get("respaldo")
            else None
        )

        def _finish_refresh_guaranteed():
            _run_script_guaranteed(check_only=True)

        def _run_convert_hsh_res():
            if not (state.get("respaldo") and cmd_convert_hsh_res):
                _finish_refresh_guaranteed()
                return
            _set_status(f"Convirtiendo HSH respaldo {state['respaldo']}...")
            _console(f">> CMD[CONVERT HSH respaldo]: {' '.join(map(str, cmd_convert_hsh_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_convert_hsh_res,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-HSH-RES"),
                on_done=lambda rc: (_finish_refresh_guaranteed() if rc == 0 else _fail(f"Conversion HSH respaldo ({state['respaldo']}) fallo")),
            )

        def _run_convert_sca_res():
            if not (state.get("respaldo") and cmd_convert_sca_res):
                _run_convert_hsh_res()
                return
            _set_status(f"Convirtiendo SCADA respaldo {state['respaldo']}...")
            _console(f">> CMD[CONVERT SCADA respaldo]: {' '.join(map(str, cmd_convert_sca_res))}", "warn")
            app.tasks.run_subprocess(
                cmd_convert_sca_res,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-SCADA-RES"),
                on_done=lambda rc: (_run_convert_hsh_res() if rc == 0 else _fail(f"Conversion SCADA respaldo ({state['respaldo']}) fallo")),
            )

        def _run_convert_hsh():
            _set_status("Convirtiendo HSH principal...")
            _console(f">> CMD[CONVERT HSH principal]: {' '.join(map(str, cmd_convert_hsh))}", "warn")
            app.tasks.run_subprocess(
                cmd_convert_hsh,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-HSH"),
                on_done=lambda rc: (_run_convert_sca_res() if rc == 0 else _fail("Conversion HSH principal fallo")),
            )

        def _run_convert_sca():
            _set_status("Convirtiendo SCADA principal...")
            _console(f">> CMD[CONVERT SCADA principal]: {' '.join(map(str, cmd_convert_sca))}", "warn")
            app.tasks.run_subprocess(
                cmd_convert_sca,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("CONVERT-SCADA"),
                on_done=lambda rc: (_run_convert_hsh() if rc == 0 else _fail("Conversion SCADA principal fallo")),
            )

        def _after_import_res(rc: int):
            if rc != 0:
                _fail("Importacion SCADA/HSH respaldo fallo")
                return
            _run_convert_sca()

        def _run_import_res():
            if not cmd_import_respaldo:
                _run_convert_sca()
                return
            _set_status(f"Sincronizando SCADA/HSH respaldo ({state['respaldo']})...")
            _console(f">> CMD[IMPORT SCADA/HSH respaldo]: {' '.join(map(str, cmd_import_respaldo))}", "warn")
            app.tasks.run_subprocess(
                cmd_import_respaldo,
                env=env,
                cwd=cwd,
                on_progress=_on_progress_factory("IMPORT-RES"),
                on_done=_after_import_res,
            )

        def _after_import_principal(rc: int):
            if rc != 0:
                _fail("Importacion SCADA/HSH principal fallo.")
                return
            _run_import_res()

        _set_status("Sincronizando SCADA/HSH (empresa principal)...")
        _console(f">> CMD[IMPORT SCADA/HSH principal]: {' '.join(map(str, cmd_import_principal))}", "warn")
        app.tasks.run_subprocess(
            cmd_import_principal,
            env=env,
            cwd=cwd,
            on_progress=_on_progress_factory("IMPORT-PRINCIPAL"),
            on_done=_after_import_principal,
        )

    def _trigger_cleanup_pipeline_guaranteed():
        """ CORREGIDO: Inicia un ciclo de reimportacion  para validar la limpieza manual."""
        state["verification_cycle"] = int(state.get("verification_cycle", 0)) + 1
        ciclo = state["verification_cycle"]
        _console(f" Ciclo de verificacion  #{ciclo}", "warn")
        _set_status("Reimportando SCADA/HSH para verificar la limpieza...", indeterminate=True)
        _run_pipeline_refresh_guaranteed()

    # Iniciar el flujo completo
    _run_pipeline_full_guaranteed()


def ejecutar_consulta_pi_cambiar_hsh(app) -> None:
    """
    Ejecuta SOLO la consulta a PI para el flujo de Cambiar SCADA Key,
    reutilizando el estado recolectado durante la ultima ejecucion del pipeline.
    """
    ventana = getattr(app, "ventana", None)

    state = getattr(app, "_cambiar_key_state", None)
    if not isinstance(state, dict):
        messagebox.showerror(
            "Consulta PI - Cambiar SCADA Key",
            "No hay estado disponible para Cambiar SCADA Key.\n\n"
            "Ejecuta primero el flujo de cambio de key.",
            parent=ventana,
        )
        return

    pi_tags = state.get("pi_tags") or {}
    tags_map = {str(emp).upper(): set(tags) for emp, tags in pi_tags.items() if tags}
    if not tags_map:
        messagebox.showwarning(
            "Consulta PI - Cambiar SCADA Key",
            "No se encontraron tags para consultar en PI.\n\n"
            "Ejecuta primero el flujo de Cambiar SCADA Key con datos validos.",
            parent=ventana,
        )
        return

    console = getattr(app, "console", None)

    # Mientras se ejecuta un nuevo flujo, la consulta PI dedicada debe reiniciarse
    try:
        setattr(app, "cambiar_key_ready_for_pi", False)
        boton_pi_tmp = getattr(app, "boton_consultar_pi_cambiar", None)
        if boton_pi_tmp is not None:
            boton_pi_tmp.config(state="disabled")
    except Exception:
        pass

    def _console(msg: str, tag: str = "info") -> None:
        if console is None:
            return
        try:
            app.ventana.after(0, lambda: console.write(msg, tag))
        except Exception:
            pass

    server_map: Dict[str, Optional[str]] = {}
    principal = state.get("empresa")
    if principal and state.get("servidor_principal"):
        server_map[str(principal).upper()] = state["servidor_principal"]  # type: ignore[index]
    respaldo_emp = state.get("respaldo")
    if respaldo_emp and state.get("servidor_respaldo"):
        server_map[str(respaldo_emp).upper()] = state["servidor_respaldo"]  # type: ignore[index]
    for emp, srv in (state.get("applied_servers") or {}).items():
        if srv:
            server_map[str(emp).upper()] = srv

    if not server_map:
        messagebox.showerror(
            "Consulta PI - Cambiar SCADA Key",
            "No se pudo determinar el mapa de servidores para la consulta a PI.\n\n"
            "Revisa la configuracion de empresas y vuelve a intentar.",
            parent=ventana,
        )
        return

    try:
        app.start_status("Consultando valores en PI (Cambiar SCADA Key)...", indeterminate=True)
    except Exception:
        pass

    try:
        result = collect_pi_snapshots(
            app=app,
            tags_by_empresa=tags_map,
            server_map=server_map,
            console_write=lambda msg, tag="info": _console(msg, tag),
            empresa_principal=str(principal).upper() if principal else None,
        )
    finally:
        try:
            app.stop_status()
        except Exception:
            pass

    # Actualizar el estado compartido con los resultados de PI
    state["pi_reports"] = list(dict.fromkeys(result.lines))
    state["pi_missing"] = list(dict.fromkeys(result.missing_lines))
    state["pi_snapshot_map"] = result.snapshot_map
    state["pi_missing_map"] = result.missing_map
    state["pi_snapshot_messages"] = result.messages
    state["pi_snapshot_collected_at"] = result.collected_at

    for line in state["pi_reports"]:
        _console(f"[PI] {line}", "info")
    for line in state["pi_missing"]:
        _console(f"[PI-MISSING] {line}", "warn")

    total_tags = sum(len(tags) for tags in tags_map.values())
    empresas = ", ".join(sorted(tags_map.keys()))
    status = "success" if not result.has_failures else "error"

    resumen = f"Empresas: {empresas}\nTags consultados: {total_tags}"

    details: List[str] = []
    if result.lines:
        details.extend(result.lines)
    if result.missing_lines:
        if details:
            details.append("")
        details.append("Tags sin datos o con errores:")
        details.extend(result.missing_lines)
    if not details:
        details.append("No se recibieron datos desde PI. Revisa la consola y los logs de PI.")

    show_summary_dialog(
        parent=ventana,
        mensaje=resumen,
        title="Consulta PI - Cambiar SCADA Key",
        status=status,
        details=details or None,
        files=None,
        show_open_file=False,
    )

