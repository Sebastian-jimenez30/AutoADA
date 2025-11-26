from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from tkinter import messagebox

from utils.cli import build_cmd
from ui.components.success_dialog import show_success_with_open

DEFAULT_MODO = "sca,hsh,ods"
CONVERT_COMPONENTS = ("sca", "hsh", "ods", "ods_csv")
CONVERT_MODE = "Buscar_keys"


def ejecutar_actualizar_datos_default(app) -> None:
    """
    Sincroniza los datos locales (SCADA / HSH / ODS) usando el perfil default de importar_all
    y luego ejecuta las conversiones correspondientes.
    Ejecuta el pipeline para todas las empresas permitidas en el entorno actual.
    """

    empresas = list(app.obtener_empresas_permitidas() or [])
    if not empresas:
        try:
            empresas = list((app.empresa_claves or {}).keys())
        except Exception:
            empresas = []

    empresas = [str(e).strip().upper() for e in empresas if e and e != "EMPRESA..."]
    if not empresas:
        messagebox.showerror("Actualizar datos", "No se encontraron empresas configuradas para actualizar.")
        return

    dominios = ["CC"]

    btn = getattr(app, "boton_actualizar_datos", None)
    original_btn_text = None
    if btn is not None:
        try:
            original_btn_text = btn.cget("text")
            btn.config(text=" Actualizando... ", state="disabled")
        except Exception:
            pass

    env = app.secure_env()
    cwd = app.base_dir

    console = getattr(app, "console", None)

    def _ui(fn):
        try:
            app.ventana.after(0, fn)
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def _write_console(msg: str, tag: str = "info") -> None:
        if console is not None:
            _ui(lambda: console.write(msg, tag))

    def _set_status(msg: str) -> None:
        if hasattr(app, "set_status"):
            _ui(lambda: app.set_status(msg))

    def _success_status(msg: str) -> None:
        if hasattr(app, "success_status"):
            _ui(lambda: app.success_status(msg))

    def _error_status(msg: str) -> None:
        if hasattr(app, "error_status"):
            _ui(lambda: app.error_status(msg))

    _write_console(">> Iniciando actualización de datos (perfil default).", "info")
    app.start_status("Sincronizando datos (perfil default)...", indeterminate=True)

    queue: List[Tuple[str, str]] = []
    errors: List[str] = []
    completed: List[str] = []

    for empresa in empresas:
        servidor: Optional[str] = None
        for dominio in dominios:
            try:
                servidor = app.generar_server(empresa, dominio)
            except Exception:
                servidor = None
            if servidor:
                break
        if not servidor:
            errors.append(f"{empresa}: no se pudo resolver servidor (dominio CC).")
            continue
        queue.append((empresa, servidor))

    if not queue:
        app.stop_status()
        if btn is not None:
            try:
                btn.config(text=original_btn_text or " Actualizar datos ", state="normal")
            except Exception:
                pass
        messagebox.showerror("Actualizar datos", "No se pudieron resolver servidores para ninguna empresa.")
        return

    refresh_fn = getattr(app, "refresh_estado_datos", None)

    def _on_progress_factory(tagname: str):
        def _inner(line: str):
            line = (line or "").strip()
            if not line:
                return
            lower = line.lower()
            tag = "info"
            if "error" in lower or "failed" in lower or "traceback" in lower:
                tag = "error"
                _error_status(f"[{tagname}] {line}")
            elif "warn" in lower or "warning" in lower:
                tag = "warn"
            elif any(token in lower for token in ("% completado", "progreso", "step", "...")):
                _set_status(f"[{tagname}] {line}")
            _write_console(f"[{tagname}] {line}", tag)
        return _inner

    def _finish():
        if btn is not None:
            try:
                btn.config(text=original_btn_text or " Actualizar datos ", state="normal")
            except Exception:
                pass
        app.stop_status()
        if callable(refresh_fn):
            try:
                refresh_fn()
            except Exception:
                pass

        if errors and not completed:
            _error_status("La actualización falló.")
            messagebox.showerror(
                "Actualizar datos",
                "No fue posible actualizar los datos:\n- " + "\n- ".join(errors),
                parent=getattr(app, "ventana", None),
            )
            return

        mensaje = []
        if completed:
            mensaje.append(f"Empresas actualizadas: {', '.join(completed)}.")
        if errors:
            mensaje.append("Empresas con errores:\n- " + "\n- ".join(errors))

        log_path = os.path.join(app.base_dir, "out", "log", "importar.log")
        files = [log_path] if os.path.exists(log_path) else []

        if errors:
            _error_status("Actualización con incidencias. Revisa detalles.")
            messagebox.showwarning(
                "Actualizar datos",
                "\n".join(mensaje),
                parent=getattr(app, "ventana", None),
            )
        else:
            _success_status("Datos sincronizados correctamente.")
            show_success_with_open(
                parent=getattr(app, "ventana", None),
                mensaje="\n".join(mensaje) if mensaje else "Datos actualizados correctamente.",
                title="Actualización de datos completada",
                files=files,
            )

    def _run_next():
        if not queue:
            _finish()
            return

        empresa, servidor = queue.pop(0)
        _set_status(f"Importando datos para {empresa} (perfil default)...")
        cmd_import = build_cmd("scripts.importar_all", servidor, empresa, DEFAULT_MODO)
        _write_console(f">> CMD[IMPORT:{empresa}]: {' '.join(map(str, cmd_import))}", "warn")

        def _after_import(rc: int):
            if rc != 0:
                errors.append(f"{empresa}: importar_all terminó con rc={rc}")
                _run_next()
                return

            component_iter = iter(CONVERT_COMPONENTS)

            def _run_convert():
                try:
                    component = next(component_iter)
                except StopIteration:
                    completed.append(empresa)
                    if callable(refresh_fn):
                        try:
                            refresh_fn()
                        except Exception:
                            pass
                    _run_next()
                    return

                _set_status(f"Convirtiendo {component.upper()} para {empresa}...")
                cmd_conv = build_cmd("scripts.Convertir_all", empresa, CONVERT_MODE, "--only", component)
                _write_console(f">> CMD[CONVERT:{empresa}:{component}]: {' '.join(map(str, cmd_conv))}", "warn")

                def _after_convert(rc_conv: int):
                    if rc_conv != 0:
                        errors.append(f"{empresa}: convertir {component} terminó con rc={rc_conv}")
                        _run_next()
                        return
                    _run_convert()

                app.tasks.run_subprocess(
                    cmd_conv,
                    env=env,
                    cwd=cwd,
                    on_progress=_on_progress_factory(f"CONVERT-{empresa}-{component.upper()}"),
                    on_done=_after_convert,
                )

            _run_convert()

        app.tasks.run_subprocess(
            cmd_import,
            env=env,
            cwd=cwd,
            on_progress=_on_progress_factory(f"IMPORT-{empresa}"),
            on_done=_after_import,
        )

    _run_next()
