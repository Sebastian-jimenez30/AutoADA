from __future__ import annotations

import os
from tkinter import messagebox

from .common import _console_factory, _mods, _on_progress_factory, _ui, build_cmd


def importar_y_convertir_unifilares(app):
    empresa = app.opcion_empresa_unifilares.get()
    dominio = app.opcion_dominio_unifilares.get()
    if empresa == "Empresa..." or dominio == "Dominio...":
        messagebox.showerror("Error", "Debe seleccionar empresa y dominio.")
        return

    servidor = app.generar_server(empresa, dominio)
    if not servidor:
        app.error_status("No se pudo resolver el servidor")
        messagebox.showerror(
            "Error",
            "No se pudo resolver el servidor para la empresa/dominio seleccionados.",
        )
        return

    btn = app.boton_importar_unifilares
    btn.config(state="disabled", text=" Importando... ")

    m = _mods()
    env = app.secure_env()
    cwd = app.base_dir
    console = _console_factory(app)

    app.start_status("Preparando importacion de unifilares...", indeterminate=True)
    if getattr(app, "console", None):
        app.console.clear()
        console(">> Consola OK. Iniciando IMPORTACION (paralelo) + CONVERSION streaming...", "info")

    usecase_scada = "validar_unifilares"
    console(f">> IMPORT usecase (SCA) = {usecase_scada}", "info")

    cmd_sca = build_cmd(m["importar"], servidor, empresa, "sca", "--usecase", usecase_scada)
    cmd_ods = build_cmd(m["importar"], servidor, empresa, "ods")
    cmd_conv_sca = build_cmd(m["convertir"], empresa, "unifilares", "--only", "sca")
    cmd_conv_ods = build_cmd(m["convertir"], empresa, "unifilares", "--only", "ods")
    cmd_conv_ods_csv = build_cmd(m["convertir"], empresa, "unifilares", "--only", "ods_csv")

    pendientes = {
        "import_sca": None,
        "import_ods": None,
        "convert_sca": None,
        "convert_ods": None,
        "convert_ods_csv": None,
    }

    def _finish(rc_final: int):
        def _end():
            btn.config(state="normal", text=" Importar ")
            if rc_final == 0:
                out_root = os.path.join(app.base_dir, "out", empresa)
                msg = (
                    "Importacion y conversion completadas.\n\n"
                    f"- SCADA   {os.path.join(out_root, 'SCADA')}\n"
                    f"- ODSTXT  {os.path.join(out_root, 'ODSTXT')}"
                )
                app.success_status("Importacion de unifilares completada")
                messagebox.showinfo("Exito", msg)
            else:
                app.error_status("El proceso termino con errores.")
                messagebox.showerror("Error", "El proceso termino con errores.")

        _ui(app, _end)

    def _maybe_finish():
        requisitos = ("import_sca", "import_ods", "convert_sca", "convert_ods", "convert_ods_csv")
        if all(pendientes[k] is not None for k in requisitos):
            ok = all(pendientes[k] == 0 for k in requisitos)
            _finish(0 if ok else 1)

    def _on_progress_pref(tag: str):
        return _on_progress_factory(app, prefix=f"[{tag}] ")

    def _lanzar_convert(component: str):
        if component == "sca":
            console(">> Lanza CONVERT (sca)", "info")
            app.tasks.run_subprocess(
                cmd_conv_sca,
                resource_key=f"{empresa}:convert:unif:sca",
                env=env,
                cwd=cwd,
                on_progress=_on_progress_pref("CONVERT-SCA"),
                on_done=lambda rc: (pendientes.update({"convert_sca": rc}), _maybe_finish()),
            )
        elif component == "ods":
            console(">> Lanza CONVERT (ods)", "info")
            app.tasks.run_subprocess(
                cmd_conv_ods,
                resource_key=f"{empresa}:convert:unif:ods",
                env=env,
                cwd=cwd,
                on_progress=_on_progress_pref("CONVERT-ODS"),
                on_done=lambda rc: _after_convert_ods(rc),
            )
        elif component == "ods_csv":
            console(">> Lanza CONVERT (ods_csv)", "info")
            app.tasks.run_subprocess(
                cmd_conv_ods_csv,
                resource_key=f"{empresa}:convert:unif:ods_csv",
                env=env,
                cwd=cwd,
                on_progress=_on_progress_pref("CONVERT-ODSCSV"),
                on_done=lambda rc: (pendientes.update({"convert_ods_csv": rc}), _maybe_finish()),
            )

    def _after_convert_ods(rc: int):
        pendientes["convert_ods"] = rc
        if rc == 0:
            _ui(app, lambda: app.set_status("Generando ODSTXT -> CSV..."))
            _lanzar_convert("ods_csv")
        else:
            pendientes["convert_ods_csv"] = 1
            _maybe_finish()

    def _on_done_ods(rc: int):
        pendientes["import_ods"] = rc
        if rc == 0:
            _ui(app, lambda: app.set_status("Convirtiendo ODS para unifilares..."))
            _lanzar_convert("ods")
        else:
            pendientes["convert_ods"] = 1
            pendientes["convert_ods_csv"] = 1
            _ui(app, lambda: app.error_status("La importacion ODS fallo; se omiten conversiones ODS."))
            _maybe_finish()

    def _on_done_sca(rc: int):
        pendientes["import_sca"] = rc
        if rc != 0:
            pendientes["convert_sca"] = 1
            _ui(app, lambda: app.error_status("La importacion SCA fallo."))
            _maybe_finish()
            return
        _ui(app, lambda: app.set_status("Convirtiendo SCADA para unifilares..."))
        _lanzar_convert("sca")

    _ui(app, lambda: app.set_status("Sincronizando datos (paralelo): SCA + ODS..."))
    app.tasks.run_subprocess(
        cmd_sca,
        resource_key=f"{empresa}:import:sca",
        env=env,
        cwd=cwd,
        on_progress=_on_progress_pref("IMPORT-SCA"),
        on_done=_on_done_sca,
    )
    app.tasks.run_subprocess(
        cmd_ods,
        resource_key=f"{empresa}:import:ods",
        env=env,
        cwd=cwd,
        on_progress=_on_progress_pref("IMPORT-ODS"),
        on_done=_on_done_ods,
    )


__all__ = ["importar_y_convertir_unifilares"]
