from __future__ import annotations

import os
from typing import List, Optional

from .common import (
    _runtime_root,
    _validar_keys,
    build_cmd,
    find_mode_data_ready,
    show_summary_dialog,
)


def ejecutar_buscar_key(app):
    empresa = app.opcion_empresa_buscar_key.get()
    dominio = app.opcion_dominio_buscar_key.get()

    keys_validas, invalidas = _validar_keys(app.cadena_buscar_key.get())
    if invalidas:
        show_summary_dialog(
            parent=app.ventana,
            mensaje="Las siguientes claves no tienen formato valido.",
            title="Buscar Key",
            status="error",
            details=[", ".join(invalidas)],
        )
        return
    if not keys_validas:
        show_summary_dialog(
            parent=app.ventana,
            mensaje="Debes indicar al menos una clave valida para continuar.",
            title="Buscar Key",
            status="info",
            details=["Formato esperado: 12345.67 o comodin %."],
        )
        return

    runtime_root = _runtime_root()
    ready, details = find_mode_data_ready(None, empresa)
    needs_update = (getattr(app, "checkbox_var", None) and app.checkbox_var.get()) or (not ready)

    topath = os.path.join(runtime_root, "out", "Find_key")
    output_file = os.path.join(topath, "Find_Key.xlsx")

    if not ready:
        if hasattr(app, "checkbox_var"):
            app.checkbox_var.set(True)
        show_summary_dialog(
            parent=app.ventana,
            mensaje="Se requiere sincronizar datos antes de continuar.",
            title="Buscar Key",
            status="info",
            details=[
                f"OUT: {'OK' if details.get('OUT') else 'FALTA'}",
                f"SCADA: {'OK' if details.get('SCADA') else 'FALTA'}",
                f"HSH: {'OK' if details.get('HSH') else 'FALTA'}",
                f"ODSTXT: {'OK' if details.get('ODSTXT') else 'FALTA'}",
            ],
        )

    btn = app.boton_buscar_key
    DEFAULT_BTN_TEXT = " Buscar "
    btn.config(text=" Buscando... ", state="disabled")

    mod_importar = "scripts.importar_all"
    mod_convertir = "scripts.Convertir_all"
    mod_buscar = "scripts.buscar_key"
    usecase = "buscar_keys"
    env = app.secure_env()

    state: dict = {"aborted": False}
    state_flags = {"completed": False}
    summary_lines: List[str] = []
    result_counts = {"with": None, "without": None}

    def _ui(fn):
        try:
            app.ventana.after(0, fn)
        except Exception:
            pass

    def _console(line: str, tag: str = "info"):
        if getattr(app, "console", None):
            _ui(lambda: app.console.write(line, tag))

    def _reset_button(text: str = DEFAULT_BTN_TEXT):
        try:
            btn.config(text=text, state="normal")
        except Exception:
            pass

    def _build_success_details(mode_label: str) -> List[str]:
        with_count = result_counts["with"]
        without_count = result_counts["without"]
        details_local = []
        if with_count is not None:
            details_local.append(f"Keys con resultado: {with_count}")
        if without_count is not None:
            details_local.append(f"Keys sin resultado: {without_count}")
        details_local.extend([
            f"Claves solicitadas: {len(keys_validas)}",
            f"Empresa: {empresa}",
            f"Modo de ejecucion: {mode_label}",
        ])
        if os.path.exists(output_file):
            details_local.append(f"Archivo generado: {os.path.basename(output_file)}")
        else:
            details_local.append("Archivo no generado.")
        return details_local

    def _finish_result(
        success: bool,
        message: str,
        details_list: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
    ) -> None:
        if state_flags["completed"]:
            return
        state_flags["completed"] = True
        state["aborted"] = True

        def _end():
            try:
                app.stop_status()
            except Exception:
                pass
            _reset_button()
            folder_ref = topath if os.path.exists(topath) else None
            dialog_files = files
            if dialog_files is None and success and os.path.exists(output_file):
                dialog_files = [output_file]
            dialog_status = "success" if success else "error"
            if success:
                app.success_status("Busqueda lista")
            else:
                app.error_status("La ejecucion termino con errores")
            show_summary_dialog(
                parent=app.ventana,
                mensaje=message,
                title="Buscar Key completada" if success else "Buscar Key con errores",
                status=dialog_status,
                details=details_list,
                files=dialog_files,
                folder=folder_ref,
                show_open_file=success,
            )

        _ui(_end)

    def _on_progress_pref(tagname: str):
        def _inner(line: str):
            line = (line or "").strip()
            if not line:
                return
            lower = line.lower()
            tag = "info"
            if "error" in lower or "failed" in lower or "traceback" in lower:
                tag = "error"
                _ui(lambda: app.error_status(f"[{tagname}] {line}"))
            elif "warn" in lower or "warning" in lower:
                tag = "warn"
            elif "%" in lower or "..." in lower or "step" in lower or "progreso" in lower:
                _ui(lambda: app.set_status(f"[{tagname}] {line}"))
            _console(f"[{tagname}] {line}", tag)
            if tagname == "BUSCAR":
                parsed = line.strip()
                if not parsed:
                    return
                capture = parsed.split("-", 1)[1].strip() if "-" in parsed else parsed
                lower_capture = capture.lower()
                if lower_capture.startswith("keys con resultado"):
                    try:
                        result_counts["with"] = int(capture.split()[-1])
                    except ValueError:
                        pass
                elif lower_capture.startswith("keys sin resultado"):
                    try:
                        result_counts["without"] = int(capture.split()[-1])
                    except ValueError:
                        pass

        return _inner

    def _fin_buscar(rc: int):
        if rc == 0:
            mode_label = "Sincronizacion completa" if needs_update else "Modo local"
            details_eff = summary_lines[:] if summary_lines else []
            if not details_eff:
                details_eff = _build_success_details(mode_label)
            else:
                details_eff.extend(_build_success_details(mode_label))
            _finish_result(True, "Busqueda completada sin errores.", details_eff)
        else:
            _finish_result(False, "La busqueda no se completo.", [f"scripts.buscar_key finalizo con codigo {rc}"])

    if not needs_update:
        _ui(lambda: app.set_status("Buscando claves modo local..."))
        cmd = build_cmd(mod_buscar, empresa, ",".join(keys_validas))
        _console(f">> CMD[BUSCAR]: {' '.join(map(str, cmd))}", "warn")
        app.tasks.run_subprocess(
            cmd,
            env=env,
            cwd=runtime_root,
            on_progress=_on_progress_pref("BUSCAR"),
            on_done=_fin_buscar,
        )
        return

    servidor = app.generar_server(empresa, dominio)
    if not servidor:
        _finish_result(
            False,
            "No se pudo resolver el servidor de la empresa o dominio.",
            [f"Empresa: {empresa}", f"Dominio: {dominio}"],
        )
        return

    app.start_status("Preparando busqueda...", indeterminate=True)
    if getattr(app, "console", None):
        app.console.clear()
        _console(">> Consola OK. Iniciando proceso (import + convert paralelos)...", "info")

    cmd_sca = build_cmd(mod_importar, servidor, empresa, "sca", "--usecase", usecase)
    cmd_hsh = build_cmd(mod_importar, servidor, empresa, "hsh", "--usecase", usecase)
    cmd_ods = build_cmd(mod_importar, servidor, empresa, "ods", "--usecase", usecase)

    _console(f">> IMPORT usecase = {usecase}", "info")
    _console(f">> CMD[IMPORT-SCA]: {' '.join(map(str, cmd_sca))}", "warn")
    _console(f">> CMD[IMPORT-HSH]: {' '.join(map(str, cmd_hsh))}", "warn")
    _console(f">> CMD[IMPORT-ODS]: {' '.join(map(str, cmd_ods))}", "warn")

    state.update({
        "import": {"sca": None, "hsh": None, "ods": None},
        "convert": {"sca": None, "hsh": None, "ods": None, "ods_csv": None},
        "buscar_started": False,
        "ods_csv_started": False,
        "mode_label": "Sincronizacion completa",
    })

    def _try_run_buscar():
        if state.get("aborted"):
            return
        if state["buscar_started"]:
            return
        if all(v == 0 for v in state["convert"].values()):
            state["buscar_started"] = True
            _ui(lambda: app.set_status("Buscando claves..."))
            cmd_bus = build_cmd(mod_buscar, empresa, ",".join(keys_validas))
            _console(f">> CMD[BUSCAR]: {' '.join(map(str, cmd_bus))}", "warn")
            app.tasks.run_subprocess(
                cmd_bus,
                env=env,
                cwd=runtime_root,
                on_progress=_on_progress_pref("BUSCAR"),
                on_done=_fin_buscar,
            )
        elif all(v is not None for v in state["convert"].values()) and any(v == 1 for v in state["convert"].values()):
            _finish_result(False, "Una o mas conversiones fallaron. Revisa la consola para mas detalles.")

    def _maybe_start_ods_csv():
        if state.get("aborted") or state["ods_csv_started"]:
            return
        if state["convert"]["ods"] == 0 and state["convert"]["sca"] == 0:
            state["ods_csv_started"] = True
            _ui(lambda: app.set_status("Convirtiendo ODSTXT -> CSV..."))
            cmd_csv = build_cmd(mod_convertir, empresa, "Buscar_keys", "--only", "ods_csv")
            _console(f">> CMD[CONVERT-ODS_CSV]: {' '.join(map(str, cmd_csv))}", "warn")
            app.tasks.run_subprocess(
                cmd_csv,
                resource_key=f"{empresa}:convert:ods_csv",
                env=env,
                cwd=runtime_root,
                on_progress=_on_progress_pref("CONVERT-ODS_CSV"),
                on_done=lambda rc2: (
                    state["convert"].__setitem__("ods_csv", 0 if rc2 == 0 else 1),
                    _try_run_buscar(),
                ),
            )

    def _start_convert(component: str):
        if state.get("aborted"):
            return
        cmd_conv = build_cmd(mod_convertir, empresa, "Buscar_keys", "--only", component)
        _console(f">> CMD[CONVERT-{component.upper()}]: {' '.join(map(str, cmd_conv))}", "warn")

        def _done_conv(rc: int, comp=component):
            if state.get("aborted"):
                return
            state["convert"][comp] = 0 if rc == 0 else 1
            if comp == "ods":
                if rc != 0:
                    state["convert"]["ods_csv"] = 1
                else:
                    _maybe_start_ods_csv()
            elif comp == "sca":
                _maybe_start_ods_csv()
            if rc != 0:
                _finish_result(False, "No se pudo completar la busqueda.", [f"Conversion {comp.upper()} fallo (rc={rc})."])
                return
            _try_run_buscar()

        app.tasks.run_subprocess(
            cmd_conv,
            resource_key=f"{empresa}:convert:{component}",
            env=env,
            cwd=runtime_root,
            on_progress=_on_progress_pref(f"CONVERT-{component.upper()}"),
            on_done=_done_conv,
        )

    def _on_done_import(component: str, rc: int):
        if state.get("aborted"):
            return
        state["import"][component] = 0 if rc == 0 else 1
        if rc == 0:
            _ui(lambda: app.set_status(f"Convirtiendo {component.upper()} despues de importar..."))
            _start_convert(component)
        else:
            state["convert"][component] = 1
            if component == "ods":
                state["convert"]["ods_csv"] = 1
            _finish_result(False, "No se pudo completar la busqueda.", [f"Importacion {component.upper()} fallo (rc={rc})."])

    _ui(lambda: app.set_status("Sincronizando datos: sca, hsh, ods..."))
    app.tasks.run_subprocess(
        cmd_sca,
        resource_key=f"{empresa}:import:sca",
        env=env,
        cwd=runtime_root,
        on_progress=_on_progress_pref("IMPORT-SCA"),
        on_done=lambda rc: _on_done_import("sca", rc),
    )
    app.tasks.run_subprocess(
        cmd_hsh,
        resource_key=f"{empresa}:import:hsh",
        env=env,
        cwd=runtime_root,
        on_progress=_on_progress_pref("IMPORT-HSH"),
        on_done=lambda rc: _on_done_import("hsh", rc),
    )
    app.tasks.run_subprocess(
        cmd_ods,
        resource_key=f"{empresa}:import:ods",
        env=env,
        cwd=runtime_root,
        on_progress=_on_progress_pref("IMPORT-ODS"),
        on_done=lambda rc: _on_done_import("ods", rc),
    )
