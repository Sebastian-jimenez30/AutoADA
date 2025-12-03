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


def _finish_with_validation_error(app, btn):

    def _end():
        btn.config(text=' Crear Senales ', state='normal')
        app.error_status('Validacion fallida. Proceso detenido.')
        error_file = os.path.join(_runtime_root(), 'out', 'validacion_errores.txt')
        errores_validacion = []
        try:
            if os.path.exists(error_file):
                with open(error_file, 'r', encoding='utf-8') as f:
                    errores_validacion = f.readlines()
                    if errores_validacion and 'Se encontraron' in errores_validacion[0]:
                        errores_validacion = errores_validacion[1:]
            else:
                log_path = os.path.join(_runtime_root(), 'log', 'Scada_load.log')
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for i in range(len(lines) - 1, -1, -1):
                            if 'Se encontraron los siguientes errores en las validaciones:' in lines[i]:
                                j = i + 1
                                while j < len(lines) and j < i + 50:
                                    if lines[j].strip().startswith('-'):
                                        errores_validacion.append(lines[j].strip())
                                    j += 1
                                break
                except Exception as e:
                    errores_validacion.append(f'No se pudieron leer los errores del log: {str(e)}')
        except Exception as e:
            errores_validacion = [f'No se pudieron leer los errores: {str(e)}']
        if not errores_validacion:
            errores_validacion = ['Error en la validacion de datos. Revisa el archivo de log para mas detalles.']
        messagebox.showerror('Error de validacion', 'Se encontraron errores en la validacion de datos:\n\n' + ''.join(errores_validacion))
    _ui(app, _end)


def ejecutar_crear_senales(app):
    archivo = getattr(app, 'archivo_crear_senales', None)
    empresa = app.opcion_empresa_crear_senales.get()
    dominio = app.opcion_dominio_crear_senales.get()
    if not archivo or not empresa or empresa == 'Empresa...':
        messagebox.showerror('Error', 'Debe seleccionar empresa y un archivo.')
        return
    btn = app.boton_crear_senales
    btn.config(text=' Creando... ', state='disabled')
    m = _mods()
    env = app.secure_env()
    runtime_root = _runtime_root()
    console = _console_factory(app)
    app.start_status('Preparando creacion de senales...', indeterminate=True)
    if getattr(app, 'console', None):
        app.console.clear()
        console('>> Consola OK. Iniciando proceso de CREAR SENALES...', 'info')

    def _finish(rc: int):

        def _end():
            btn.config(text=' Crear Senales ', state='normal')
            if rc == 0:
                load_dir = os.path.join(app.base_dir, 'out', 'Load')
                files = [os.path.join(load_dir, '10_SCADA.csv'), os.path.join(load_dir, '32_FEP.csv'), os.path.join(load_dir, 'Senales_with_keys.xlsx')]
                app.success_status('Creacion de senales completada')
                show_success_with_open(parent=app.ventana, mensaje='Proceso de creacion de senales completado exitosamente.\n\nSe generaron los siguientes archivos:', title='Creacion completada', files=files, show_open_file=True)
            else:
                app.error_status('El proceso de creacion termino con errores.')
                messagebox.showerror('Error', 'El proceso termino con errores.')
        _ui(app, _end)
    needs_update = bool(getattr(app, 'checkbox_var_crear', None) and app.checkbox_var_crear.get())
    if needs_update:
        servidor = app.generar_server(empresa, dominio)
        if not servidor:
            btn.config(text=' Crear Senales ', state='normal')
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
                _ui(app, lambda: btn.config(text=' Crear Senales ', state='normal'))
                return
            _ui(app, lambda: app.set_status('Escaneando archivo de senales...'))
            cmd_scan = build_cmd(m['scan_data'], archivo, empresa, '--dominio', dominio)
            console(f">> CMD[SCAN]: {' '.join(map(str, cmd_scan))}", 'warn')
            app.tasks.run_subprocess(cmd_scan, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[SCAN] '), on_done=lambda rc3: (_ui(app, lambda: app.set_status('Generando SCADA S-A...' if rc3 == 0 else 'Validacion fallida')), (lambda: _finish_with_validation_error(app, btn) if rc3 == 2 else (lambda cmd4: (console(f">> CMD[SCADA_S-A]: {' '.join(map(str, cmd4))}", 'warn'), app.tasks.run_subprocess(cmd4, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[SCADA S-A] '), on_done=_finish)))(build_cmd(m['scada_sa'], empresa)) if rc3 == 0 else _finish(rc3))()))
            app.tasks.run_subprocess(cmd_scan, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[SCAN] '), on_done=lambda rc3: (_ui(app, lambda: app.set_status('Generando SCADA S-A...' if rc3 == 0 else 'Validacion fallida')), (lambda: _finish_with_validation_error(app, btn) if rc3 == 2 else (lambda cmd4: (console(f">> CMD[SCADA_S-A]: {' '.join(map(str, cmd4))}", 'warn'), app.tasks.run_subprocess(cmd4, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[SCADA S-A] '), on_done=_finish)))(build_cmd(m['scada_sa'], empresa, '--dominio', dominio)) if rc3 == 0 else _finish(rc3))()))

        def _after_import(rc1: int):
            if rc1 != 0:
                _ui(app, lambda: app.error_status('Fallo la importacion SCADA. Revisa la consola.'))
                _ui(app, lambda: btn.config(text=' Crear Senales ', state='normal'))
                return
            _ui(app, lambda: app.set_status('Convirtiendo datos para jobs...'))
            console(f">> CMD[CONVERT]: {' '.join(map(str, cmd_convert))}", 'warn')
            app.tasks.run_subprocess(cmd_convert, resource_key=f'{empresa}:convert:jobs', env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[CONVERT] '), on_done=_after_convert)
        _ui(app, lambda: app.set_status('Sincronizando datos: importar (sca)...'))
        console(f">> CMD[IMPORT]: {' '.join(map(str, cmd_import))}", 'warn')
        app.tasks.run_subprocess(cmd_import, resource_key=f'{empresa}:import:sca', env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[IMPORT] '), on_done=_after_import)
    else:
        _ui(app, lambda: app.set_status('Escaneando archivo de senales (modo local)...'))
        cmd_scan = build_cmd(m['scan_data'], archivo, empresa, '--dominio', dominio)
        console(f">> CMD[SCAN]: {' '.join(map(str, cmd_scan))}", 'warn')
        app.tasks.run_subprocess(cmd_scan, env=env, cwd=_runtime_root(), on_progress=_on_progress_factory(app, prefix='[SCAN] '), on_done=lambda rc3: (_ui(app, lambda: app.set_status('Generando SCADA S-A...' if rc3 == 0 else 'Validacion fallida')), (lambda: _finish_with_validation_error(app, btn) if rc3 == 2 else (lambda cmd4: (console(f">> CMD[SCADA_S-A]: {' '.join(map(str, cmd4))}", 'warn'), app.tasks.run_subprocess(cmd4, env=env, cwd=_runtime_root(), on_progress=_on_progress_factory(app, prefix='[SCADA S-A] '), on_done=_finish)))(build_cmd(m['scada_sa'], empresa, '--dominio', dominio)) if rc3 == 0 else _finish(rc3))()))


__all__ = ["ejecutar_crear_senales"]


