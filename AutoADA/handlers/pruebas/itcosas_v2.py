from __future__ import annotations

import os
import shutil
from datetime import datetime
from tkinter import messagebox

from .common import (
    _console_factory,
    _mods,
    _on_progress_factory,
    _runtime_root,
    _ui,
    _valid_date,
    _valid_time_ms,
    build_cmd,
    output_root,
    project_root,
    show_success_with_open,
)

def ejecutar_pruebas_itcosas_v2_pipeline(app):
    """

    Pipeline completo (itcosas v2):

      A) SOE Local v2 (desde SOE_SE*.csv en cwd) -> SOE_Local.csv

      B) HIS (ODBC) multi-station opcional -> consolida en out/pruebas/data.csv y copia data-HIS.csv (prefijo 'data-')

      C) SOE Monarch v2 (SCADA + data[-HIS].csv) -> SOE_Monarch.csv

      D) Checklist v2 -> SOE_completo.xlsx (o el nombre que entregue el script v2)



    A y B corren en paralelo. C espera A y B. D espera C.

    """
    empresa = app.opcion_empresa_pyp.get() if hasattr(app, 'opcion_empresa_pyp') else None
    if not empresa or empresa == 'Empresa...':
        messagebox.showerror('Error', 'Selecciona la empresa.')
        return
    checklist = getattr(app, 'pyp_checklist_file', None)
    soe_se = getattr(app, 'pyp_soe_se_file', None)
    if not (checklist and os.path.isfile(checklist) and soe_se and os.path.isfile(soe_se)):
        messagebox.showerror('Faltan archivos', 'Debes seleccionar Checklist y el CSV base SOE_SE (v2).')
        return
    fecha = (app.pyp_fecha.get() or '').strip()
    hini = (app.pyp_hora_inicio.get() or '').strip()
    hfin = (app.pyp_hora_fin.get() or '').strip()
    if not _valid_date(fecha) or not _valid_time_ms(hini) or (not _valid_time_ms(hfin)):
        messagebox.showerror('Error', 'Fecha/Hora invalidas. Formatos: YYYY-MM-DD y HH:MM:SS.mmm')
        return
    try:
        t0 = datetime.strptime(f'{fecha} {hini}', '%Y-%m-%d %H:%M:%S.%f')
        t1 = datetime.strptime(f'{fecha} {hfin}', '%Y-%m-%d %H:%M:%S.%f')
        if t0 > t1:
            messagebox.showerror('Error', 'Hora inicio no puede ser mayor que hora fin.')
            return
    except Exception:
        messagebox.showerror('Error', 'Fecha u hora con formato invalido.')
        return
    raw_station_sel = (getattr(app, 'pyp_station_selected', None).get() if hasattr(app, 'pyp_station_selected') else '') or ''
    station_sel = raw_station_sel.strip()
    station_names = getattr(app, 'pyp_station_names', []) if hasattr(app, 'pyp_station_names') else []
    placeholder_values = {'estacion...', 'estacion...'}
    if station_sel and station_sel.lower() not in placeholder_values:
        stations = [station_sel]
    else:
        stations = [(s or '').strip() for s in station_names if (s or '').strip()]
    seen_stations = set()
    deduped: list[str] = []
    for st in stations:
        if st not in seen_stations:
            seen_stations.add(st)
            deduped.append(st)
    stations = deduped
    if not stations:
        messagebox.showerror('Faltan estaciones', 'No hay estaciones definidas (ni seleccionada ni en checklist). Para v2 se requiere HIS; agrega una estacion o completa el checklist con Station Name.')
        return
    env = app.secure_env()
    outdir = os.path.join(output_root(), 'out', 'pruebas')
    os.makedirs(outdir, exist_ok=True)
    runtime_root = _runtime_root()
    m = _mods()
    console = _console_factory(app)
    if getattr(app, 'console', None):
        app.console.clear()
    app.start_status('Iniciando pipeline (itcosas v2)...', indeterminate=True)
    console('>> Pipeline itcosas v2 - Inicio', 'info')
    for fname in ('SOE_Local.csv', 'SOE_Monarch.csv', 'SOE_completo.xlsx', 'data.csv', 'data-HIS.csv'):
        fpath = os.path.join(outdir, fname)
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass
    try:
        dst_soese = os.path.join(outdir, os.path.basename(soe_se))
        if os.path.abspath(soe_se) != os.path.abspath(dst_soese):
            shutil.copy2(soe_se, dst_soese)
    except Exception as e:
        messagebox.showerror('Error', f'No se pudo copiar SOE_SE al area de trabajo: {e}')
        return
    state = {'soe_local': None, 'his': None, 'his_done_count': 0, 'his_total': 1 if stations else 0, 'soe_monarch': None, 'checklist': None}
    artifacts = {'soe_local': os.path.join(outdir, 'SOE_Local.csv'), 'his_data': os.path.join(outdir, 'data.csv'), 'his_data_v2': os.path.join(outdir, 'data-HIS.csv'), 'soe_monarch': os.path.join(outdir, 'SOE_Monarch.csv'), 'soe_final': os.path.join(outdir, 'SOE_completo.xlsx')}

    def _station_arg(stations_list: list[str]) -> str:
        if not stations_list:
            return '%'
        return ','.join(stations_list)

    def _copy_to_data_his():
        try:
            if os.path.exists(artifacts['his_data']):
                shutil.copy2(artifacts['his_data'], artifacts['his_data_v2'])
                return True
        except Exception as e:
            console(f'[HIS] No se pudo crear data-HIS.csv: {e}', 'warn')
        return False

    def _run_his(stations_list: list[str]):
        station_arg = _station_arg(stations_list)
        args = [m['his_soe'], empresa, '--station', station_arg, '--fecha', fecha, '--hora_inicio', hini, '--hora_fin', hfin, '--outdir', outdir]
        cmd = build_cmd(*args)
        label = station_arg if station_arg != '%' else 'todas'
        console(f">> CMD[HIS:{label}]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=project_root(), on_progress=_on_progress_factory(app, prefix='[HIS] '), on_done=lambda rc: _on_done_his(0 if rc == 0 else 1))

    def _on_done_his(code: int):
        state['his_done_count'] = state['his_total']
        if code == 0 and os.path.exists(artifacts['his_data']):
            state['his'] = 0
            copied = _copy_to_data_his()
            if copied:
                _ui(app, lambda: app.success_status('HIS OK (consulta unica)'))
            else:
                _ui(app, lambda: app.success_status('HIS OK, sin data-HIS.csv auxiliar'))
        elif code == 0:
            state['his'] = 1
            _ui(app, lambda: app.error_status('HIS completo pero no genero data.csv'))
        else:
            state['his'] = 1
            _ui(app, lambda: app.error_status('HIS fallo.'))
        _check_and_maybe_continue()

    def _run_soe_local_v2():
        input_path = os.path.abspath(soe_se)
        cmd = build_cmd(m['soe_local_v2'], f'--input={input_path}', f'--outdir={outdir}')
        console(f">> CMD[SOE_LOCAL_V2]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=project_root(), on_progress=_on_progress_factory(app, prefix='[SOE_LOCAL_V2] '), on_done=lambda rc: _on_done_soe_local_v2(0 if rc == 0 else 1))

    def _on_done_soe_local_v2(code: int):
        state['soe_local'] = code
        if code != 0:
            _ui(app, lambda: app.error_status('Paso SOE Local v2 fallo.'))
        else:
            _ui(app, lambda: app.success_status('SOE_Local.csv (v2) generado'))
        _check_and_maybe_continue()

    def _run_soe_monarch_v2():
        scada_dir = os.path.join(output_root(), 'out', empresa, 'SCADA')
        his_path = artifacts['his_data'] if os.path.exists(artifacts['his_data']) else artifacts['his_data_v2']
        faltantes = []
        for fname in ('32_10.csv', '10_4.csv', '19_1.csv'):
            if not os.path.isfile(os.path.join(scada_dir, fname)):
                faltantes.append(fname)
        if faltantes:
            messagebox.showerror('SCADA incompleto', f'Faltan archivos en {scada_dir}:\n- ' + '\n- '.join(faltantes) + '\nActualiza SCADA antes de continuar.')
            state['soe_monarch'] = 1
            _check_and_maybe_continue()
            return
        if not (os.path.exists(artifacts['his_data']) or os.path.exists(artifacts['his_data_v2'])):
            messagebox.showerror('Falta data (HIS)', 'No se encontro data.csv / data-HIS.csv en out/pruebas.')
            state['soe_monarch'] = 1
            _check_and_maybe_continue()
            return
        cmd_args = [m['soe_monarch_v2'], empresa, f'--scada={scada_dir}', f'--his={his_path}', f'--outdir={outdir}', f'--checklist={checklist}']
        if stations:
            cmd_args.append(f'--station={stations[0]}')
        cmd = build_cmd(*cmd_args)
        console(f">> CMD[SOE_MONARCH_V2]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=project_root(), on_progress=_on_progress_factory(app, prefix='[SOE_MONARCH_V2] '), on_done=lambda rc: _on_done_soe_monarch_v2(0 if rc == 0 else 1))

    def _on_done_soe_monarch_v2(code: int):
        state['soe_monarch'] = code
        if code == 0:
            _ui(app, lambda: app.success_status('SOE_Monarch.csv (v2) generado'))
            _run_checklist_v2()
        else:
            _ui(app, lambda: app.error_status('SOE Monarch v2 fallo.'))
            _check_and_maybe_continue()

    def _run_checklist_v2(abrir_excel: bool=False):
        args = [f'--checklist={checklist}', f"--soe_local={artifacts['soe_local']}", f"--soe_monarch={artifacts['soe_monarch']}", f'--outdir={outdir}']
        if abrir_excel:
            args.append('--abrir-excel')
        cmd = build_cmd(m['checklist_v2'], *args)
        console(f">> CMD[CHECKLIST_V2]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=project_root(), on_progress=_on_progress_factory(app, prefix='[CHECKLIST_V2] '), on_done=lambda rc: _on_done_checklist_v2(0 if rc == 0 else 1))

    def _on_done_checklist_v2(code: int):
        state['checklist'] = code
        if code == 0:
            _ui(app, lambda: app.success_status('Checklist v2 completado'))
            _final_success_dialog()
        else:
            _ui(app, lambda: app.error_status('Checklist v2 fallo.'))
            _final_failure_dialog()

    def _check_and_maybe_continue():
        if state['soe_monarch'] is None:
            if state['soe_local'] == 0 and state['his'] == 0:
                _run_soe_monarch_v2()
        if state['soe_monarch'] in (0, 1) and state['checklist'] in (0, 1):
            if state['soe_monarch'] == 0 and state['checklist'] == 0:
                _final_success_dialog()
            else:
                _final_failure_dialog()

    def _final_success_dialog():
        files = []
        for p in (artifacts['soe_local'], artifacts['his_data'], artifacts['his_data_v2'], artifacts['soe_monarch'], artifacts['soe_final']):
            if os.path.exists(p):
                files.append(p)
        if files:
            show_success_with_open(parent=app.ventana, mensaje='Pipeline v2 completado con exito.', title='Pruebas PyP - itcosas v2', files=files)
        else:
            messagebox.showinfo('Pipeline v2 completado', 'Proceso finalizado.', parent=app.ventana)

    def _final_failure_dialog():
        messagebox.showerror('Pipeline v2 incompleto', 'Uno o mas pasos fallaron. Revisa la consola para mas detalles.', parent=app.ventana)
    _run_soe_local_v2()
    _run_his(stations)

__all__ = ["ejecutar_pruebas_itcosas_v2_pipeline"]


