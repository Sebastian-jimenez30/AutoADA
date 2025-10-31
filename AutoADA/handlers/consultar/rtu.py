from __future__ import annotations

import os
from tkinter import messagebox

from ui.components.success_dialog import show_success_with_open
from utils.cli import build_cmd


def ejecutar_consulta_rtu(app):
    empresa_var = getattr(app, "opcion_empresa_consultar", None)
    empresa = empresa_var.get() if empresa_var else ""
    if not empresa or empresa == "Empresa...":
        messagebox.showerror(
            "Empresa requerida",
            "Selecciona una empresa antes de consultar.",
            parent=app.ventana,
        )
        return

    listbox = getattr(app, "rtu_listbox", None)
    current_options = getattr(app, "rtu_current_options", [])
    if listbox is None or not current_options:
        messagebox.showerror(
            "RTU/SAS",
            "No hay RTU/SAS disponibles para esta empresa.",
            parent=app.ventana,
        )
        return

    indices = listbox.curselection()
    if not indices:
        messagebox.showerror(
            "RTU/SAS",
            "Selecciona al menos una RTU o SAS.",
            parent=app.ventana,
        )
        return

    selected_rtus = [current_options[idx] for idx in indices]
    rtu_argument = ", ".join(selected_rtus)

    btn = getattr(app, "boton_consultar_rtu", None)
    if btn is not None:
        btn.config(text=" Consultando... ", state="disabled")

    if getattr(app, "console", None):
        app.console.clear()

    app.start_status("Consultando RTU/SAS", indeterminate=True)
    env = app.secure_env()
    cmd = build_cmd("scripts.consultar_rtu", "--empresa", empresa, "--rtus", rtu_argument)

    report_holder: dict[str, str | None] = {"path": None}

    def _on_progress(line: str):
        line = (line or "").strip()
        if not line:
            return

        lower = line.lower()
        tag = "info"
        if "error" in lower:
            tag = "error"
            app.error_status(line)
        elif "archivo generado exitosamente" in lower or "consultando" in lower:
            app.set_status(line)

        if "rtu_report:" in lower:
            _, payload = line.split("RTU_REPORT:", 1)
            report_holder["path"] = payload.strip()

        if getattr(app, "console", None):
            try:
                app.console.write(line, tag)
            except Exception:
                app.console.write(line)

    def _on_done(rc: int):
        def finish():
            if btn is not None:
                btn.config(text=" Consultar RTU ", state="normal")
            app.stop_status()

            if rc == 0:
                app.success_status("Consulta RTU lista")
                path = report_holder.get("path")
                if path and not os.path.isabs(path):
                    path = os.path.join(app.base_dir, path)
                if path and os.path.exists(path):
                    show_success_with_open(
                        parent=app.ventana,
                        mensaje="Consulta RTU lista.",
                        files=[path],
                    )
                else:
                    messagebox.showinfo(
                        "Consulta lista",
                        "Listo. Revisa la consola para ver el archivo.",
                        parent=app.ventana,
                    )
            else:
                app.error_status("Consulta RTU termino con errores")
                messagebox.showerror(
                    "Error",
                    "El proceso termino con errores. Revisa la consola.",
                    parent=app.ventana,
                )

        app.ventana.after(0, finish)

    app.tasks.run_subprocess(
        cmd,
        env=env,
        cwd=app.base_dir,
        resource_key=f"consultar_rtu:{empresa}",
        on_progress=_on_progress,
        on_done=_on_done,
    )


__all__ = ["ejecutar_consulta_rtu"]
