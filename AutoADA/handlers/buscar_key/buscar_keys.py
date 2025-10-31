from __future__ import annotations

import os

from .common import (
    _runtime_root,
    build_cmd,
    find_mode_data_ready,
    messagebox,
    show_success_with_open,
)


def ejecutar_buscar_keys(app):
    empresa = app.opcion_empresa_buscar_keys.get()
    dominio = app.opcion_dominio_buscar_keys.get()
    archivo = getattr(app, "archivo_excel_buscar_keys", None)

    if not archivo:
        messagebox.showerror("Error", "Selecciona un archivo Excel.")
        return

    runtime_root = _runtime_root()
    ready, details = find_mode_data_ready(None, empresa)
    needs_update = (getattr(app, "checkbox_var_keys", None) and app.checkbox_var_keys.get()) or (not ready)

    topath = os.path.join(runtime_root, "out", "Find_key")
    base_name = os.path.splitext(os.path.basename(archivo))[0] if archivo else "Find_Keys"
    output_file = os.path.join(topath, f"{base_name}_results.xlsx")

    if not ready:
        if hasattr(app, "checkbox_var_keys"):
            app.checkbox_var_keys.set(True)
        msg = (
            "No hay datos locales suficientes en el OUT del ejecutable. "
            "Se realizará actualización de BD antes de buscar.\n"
            f"- OUT: {'OK' if details.get('OUT') else 'FALTA'}\n"
            f"- SCADA: {'OK' if details.get('SCADA') else 'FALTA'}\n"
            f"- HSH: {'OK' if details.get('HSH') else 'FALTA (groups.csv y lookup_table.csv)'}\n"
            f"- ODSTXT: {'OK' if details.get('ODSTXT') else 'FALTA'}"
        )
        messagebox.showinfo("Actualización requerida", msg)

    btn = app.boton_buscar_keys
    btn.config(text=" Buscando... ", state="disabled")

    mod_importar = "scripts.importar_all"
    mod_convertir = "scripts.Convertir_all"
    mod_buscarkeys = "scripts.buscar_keys"
    usecase = "buscar_keys"
    env = app.secure_env()

    def _ui(fn):
        try:
            app.ventana.after(0, fn)
        except Exception:
            pass

    def _console(line: str, tag: str = "info"):
        if getattr(app, "console", None):
            _ui(lambda: app.console.write(line, tag))

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
            elif "%" in line or "..." in line or "step" in lower or "progreso" in lower:
                _ui(lambda: app.set_status(f"[{tagname}] {line}"))
            _console(f"[{tagname}] {line}", tag)

        return _inner

    def _fin_buscar(rc: int):
        def _end():
            btn.config(text=" ¡Realizado! " if rc == 0 else " Error ", state="normal")
            if rc == 0:
                app.success_status("Búsqueda desde archivo lista")
                result_files = []
                if os.path.exists(topath):
                    for nombre in os.listdir(topath):
                        if nombre.endswith(".xlsx") and "Find" in nombre:
                            result_files.append(os.path.join(topath, nombre))
                mensaje = (
                    "Búsqueda desde archivo lista exitosamente.\n\n"
                    f"Procesado: {os.path.basename(archivo) if archivo else 'archivo'}"
                )
                show_success_with_open(
                    parent=app.ventana,
                    mensaje=mensaje,
                    title="Búsqueda desde archivo lista",
                    folder=topath,
                    files=result_files,
                )
            else:
                app.error_status("La ejecución terminó con errores.")

        _ui(_end)

    if not needs_update:
        _ui(lambda: app.set_status("Buscando claves desde archivo modo local..."))
        cmd = build_cmd(mod_buscarkeys, empresa, archivo)
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
        btn.config(text=" Error ", state="normal")
        messagebox.showerror("Error", "No se pudo resolver el servidor de la empresa o dominio.")
        app.error_status("No se pudo resolver el servidor")
        return

    app.start_status("Preparando búsqueda desde archivo...", indeterminate=True)
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

    state = {
        "import": {"sca": None, "hsh": None, "ods": None},
        "convert": {"sca": None, "hsh": None, "ods": None, "ods_csv": None},
        "buscar_started": False,
        "ods_csv_started": False,
    }

    def _try_run_buscar():
        if state["buscar_started"]:
            return
        if all(v == 0 for v in state["convert"].values()):
            state["buscar_started"] = True
            _ui(lambda: app.set_status("Buscando claves desde archivo..."))
            cmd_bus = build_cmd(mod_buscarkeys, empresa, archivo)
            _console(f">> CMD[BUSCAR]: {' '.join(map(str, cmd_bus))}", "warn")
            app.tasks.run_subprocess(
                cmd_bus,
                env=env,
                cwd=runtime_root,
                on_progress=_on_progress_pref("BUSCAR"),
                on_done=_fin_buscar,
            )
        elif all(v is not None for v in state["convert"].values()) and any(v == 1 for v in state["convert"].values()):
            _ui(lambda: app.error_status("Una o más conversiones fallaron. Revisa la consola."))
            _ui(lambda: btn.config(text=" Error ", state="normal"))

    def _maybe_start_ods_csv():
        if state["ods_csv_started"]:
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
                on_done=lambda rc2: (state["convert"].__setitem__("ods_csv", 0 if rc2 == 0 else 1), _try_run_buscar()),
            )

    def _start_convert(component: str):
        cmd_conv = build_cmd(mod_convertir, empresa, "Buscar_keys", "--only", component)
        _console(f">> CMD[CONVERT-{component.upper()}]: {' '.join(map(str, cmd_conv))}", "warn")

        def _done_conv(rc: int, comp=component):
            state["convert"][comp] = 0 if rc == 0 else 1
            if comp == "ods":
                if rc != 0:
                    state["convert"]["ods_csv"] = 1
                else:
                    _maybe_start_ods_csv()
            elif comp == "sca":
                _maybe_start_ods_csv()
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
        state["import"][component] = 0 if rc == 0 else 1
        if rc == 0:
            _ui(lambda: app.set_status(f"Convirtiendo {component.upper()} después de importar..."))
            _start_convert(component)
        else:
            state["convert"][component] = 1
            if component == "ods":
                state["convert"]["ods_csv"] = 1
            _try_run_buscar()

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

