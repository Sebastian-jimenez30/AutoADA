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
    cmd_conv = build_cmd(m["convertir"], empresa, "unifilares", "--only", "sca,ods,ods_csv")

    pendientes = {"sca": None, "ods": None, "conv": None}
    conversion_lanzada = {"ok": False}

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
        if pendientes["sca"] is not None and pendientes["conv"] is not None:
            rc_final = 0 if pendientes["sca"] == 0 and pendientes["conv"] == 0 else 1
            _finish(rc_final)

    def _on_progress_pref(tag: str):
        return _on_progress_factory(app, prefix=f"[{tag}] ")

    def _on_done_ods(rc: int):
        pendientes["ods"] = rc
        if rc == 0:
            if not conversion_lanzada["ok"]:
                conversion_lanzada["ok"] = True
                _ui(app, lambda: app.set_status("Convirtiendo datos para unifilares..."))
                console(">> Lanza CONVERT (ods,ods_csv)", "info")
                app.tasks.run_subprocess(
                    cmd_conv,
                    resource_key=f"{empresa}:convert:unif",
                    env=env,
                    cwd=cwd,
                    on_progress=_on_progress_pref("CONVERT"),
                    on_done=lambda rc_conv: (pendientes.update({"conv": rc_conv}), _maybe_finish()),
                )
        else:
            pendientes["conv"] = 1
            _ui(app, lambda: app.error_status("La importacion ODS fallo; se omite conversion."))
            _maybe_finish()

    def _on_done_sca(rc: int):
        pendientes["sca"] = rc
        if rc != 0:
            _ui(app, lambda: app.error_status("La importacion SCA fallo."))
        _maybe_finish()

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
