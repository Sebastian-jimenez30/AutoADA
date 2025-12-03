from __future__ import annotations

import os
from tkinter import messagebox

from .common import (
    _console_factory,
    _mods,
    _on_progress_factory,
    _runtime_root,
    _ui,
    build_cmd,
    show_success_with_open,
)


def ejecutar_cambiar_nombre_senales(app):
    archivo = getattr(app, 'archivo_cambiar_nombre', None)
    empresa = app.opcion_empresa_cambiar_nombre.get()
    dominio = app.opcion_dominio_cambiar_nombre.get()
    if not archivo or not empresa or empresa == 'Empresa...':
        messagebox.showerror('Error', 'Debe seleccionar empresa y un archivo.')
        return
    btn = app.boton_cambiar_nombre
    btn.config(text=' Cambiando nombre... ', state='disabled')
    m = _mods()
    env = app.secure_env()
    runtime_root = _runtime_root()
    console = _console_factory(app)
    app.start_status('Preparando cambio de nombre de senales...', indeterminate=True)
    if getattr(app, 'console', None):
        app.console.clear()
        console('>> Consola OK. Iniciando proceso de CAMBIO DE NOMBRE...', 'info')

    def _finish(rc: int):

        def _end():
            btn.config(text=' Cambiar Nombre ', state='normal')
            if rc == 0:
                out_del = os.path.join(app.base_dir, 'out', 'Name')
                files = [os.path.join(out_del, 'change_key.csv')]
                files = [f for f in files if os.path.exists(f)]
                app.success_status('Cambio de nombre completado')
                show_success_with_open(parent=app.ventana, mensaje='Proceso de cambio de nombre completado exitosamente.', title='Cambio de nombre completado', files=files, show_open_file=True)
            else:
                app.error_status('El proceso de cambio de nombre termino con errores.')
                messagebox.showerror('Error', 'El proceso termino con errores.')
        _ui(app, _end)
    needs_update = bool(getattr(app, 'checkbox_var_cambiar_nombre', None) and app.checkbox_var_cambiar_nombre.get())
    if needs_update:
        servidor = app.generar_server(empresa, dominio)
        if not servidor:
            btn.config(text=' Cambiar Nombre ', state='normal')
            app.error_status('No se pudo resolver el servidor')
            messagebox.showerror('Error', 'No se pudo resolver el servidor para la empresa/dominio seleccionados.')
            return
        usecase = 'jobs_crear_senales'
        cmd_import = build_cmd(m['importar'], servidor, empresa, 'sca', '--usecase', usecase, '--dominio', dominio)
        cmd_convert = build_cmd(m['convertir'], empresa, 'jobs', '--dominio', dominio)
        console(f'>> IMPORT usecase = {usecase}', 'info')

        def _after_convert(rc2: int):
            if rc2 != 0:
                _ui(app, lambda: app.error_status('Fallo la conversion para jobs. Revisa la consola.'))
                _ui(app, lambda: btn.config(text=' Cambiar Nombre ', state='normal'))
                return
            _ui(app, lambda: app.set_status('Aplicando cambio de nombre...'))
            cmd_change = build_cmd(m['cambiar_nombre'], archivo, empresa, '--dominio', dominio)
            console(f">> CMD[CAMBIO]: {' '.join(map(str, cmd_change))}", 'warn')
            app.tasks.run_subprocess(cmd_change, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[CAMBIO] '), on_done=_finish)

        def _after_import(rc1: int):
            if rc1 != 0:
                _ui(app, lambda: app.error_status('Fallo la importacion SCADA. Revisa la consola.'))
                _ui(app, lambda: btn.config(text=' Cambiar Nombre ', state='normal'))
                return
            _ui(app, lambda: app.set_status('Convirtiendo datos para jobs...'))
            console(f">> CMD[CONVERT]: {' '.join(map(str, cmd_convert))}", 'warn')
            app.tasks.run_subprocess(cmd_convert, resource_key=f'{empresa}:convert:jobs', env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[CONVERT] '), on_done=_after_convert)
        _ui(app, lambda: app.set_status('Sincronizando datos: importar (sca)...'))
        console(f">> CMD[IMPORT]: {' '.join(map(str, cmd_import))}", 'warn')
        app.tasks.run_subprocess(cmd_import, resource_key=f'{empresa}:import:sca', env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[IMPORT] '), on_done=_after_import)
    else:
        _ui(app, lambda: app.set_status('Aplicando cambio de nombre (modo local)...'))
        cmd_change = build_cmd(m['cambiar_nombre'], archivo, empresa, '--dominio', dominio)
        console(f">> CMD[CAMBIO]: {' '.join(map(str, cmd_change))}", 'warn')
        app.tasks.run_subprocess(cmd_change, env=env, cwd=_runtime_root(), on_progress=_on_progress_factory(app, prefix='[CAMBIO] '), on_done=_finish)


__all__ = ["ejecutar_cambiar_nombre_senales"]


