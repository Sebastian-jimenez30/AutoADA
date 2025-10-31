from __future__ import annotations

import os
from tkinter import messagebox

from ui.components.success_dialog import show_success_with_open

from .common import _console_factory, _mods, _on_progress_factory, _ui, build_cmd


def ejecutar_validaciones_unifilares(app):
    archivos = getattr(app, "archivos_unifilares", None)
    empresa = app.opcion_empresa_unifilares.get()
    if not archivos or empresa == "Empresa...":
        messagebox.showerror("Error", "Debe seleccionar empresa y al menos un archivo.")
        return

    archivos = [str(a) for a in archivos if a]
    btn = app.boton_ejecutar_unifilares
    btn.config(text=" Ejecutando... ", state="disabled")

    m = _mods()
    env = app.secure_env()
    cwd = app.base_dir
    console = _console_factory(app)

    app.start_status("Preparando validaciones de unifilares...", indeterminate=True)
    if getattr(app, "console", None):
        app.console.clear()
        console(">> Consola OK. Iniciando VALIDACIONES de unifilares...", "info")

    def _finish(rc: int):
        def _end():
            btn.config(text=" Ejecutar ", state="normal")
            if rc == 0:
                out_dir = os.path.join(app.base_dir, "out", "Validacion_Unifilares")
                app.success_status("Validaciones de unifilares completadas")
                if os.path.exists(out_dir):
                    archivos_resultado: list[str] = []
                    for archivo in os.listdir(out_dir):
                        if archivo.endswith((".xlsx", ".csv", ".txt")) and "validacion" in archivo.lower():
                            archivos_resultado.append(os.path.join(out_dir, archivo))
                    if not archivos_resultado:
                        for archivo in os.listdir(out_dir):
                            if archivo.endswith((".xlsx", ".csv")):
                                archivos_resultado.append(os.path.join(out_dir, archivo))
                    if archivos_resultado:
                        mensaje = (
                            f"Validaciones de unifilares completadas exitosamente para {empresa}.\n\n"
                            f"Se procesaron {len(archivos)} archivo(s) de entrada.\n"
                            f"Se generaron {len(archivos_resultado)} reporte(s) de validacion."
                        )
                        show_success_with_open(
                            parent=app.ventana,
                            mensaje=mensaje,
                            title="Validaciones de unifilares completadas",
                            files=archivos_resultado,
                        )
                    else:
                        messagebox.showinfo(
                            "Validaciones completadas",
                            f"Validaciones completadas para {empresa}.\nRevisa la carpeta de salida: {out_dir}",
                            parent=app.ventana,
                        )
                else:
                    messagebox.showinfo(
                        "Validaciones completadas",
                        "Validaciones finalizadas. Revisa la consola para mas detalles.",
                        parent=app.ventana,
                    )
            else:
                app.error_status("El proceso termino con errores.")
                messagebox.showerror("Error", "El proceso termino con errores.")

        _ui(app, _end)

    cmd = build_cmd(m["validar"], "--archivos", *archivos, "--empresa", empresa)
    app.tasks.run_subprocess(
        cmd,
        env=env,
        cwd=cwd,
        on_progress=_on_progress_factory(app, prefix="[VALIDAR] "),
        on_done=_finish,
    )


__all__ = ["ejecutar_validaciones_unifilares"]
