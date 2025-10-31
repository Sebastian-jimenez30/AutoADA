from __future__ import annotations

import os
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
    show_success_with_open,
)

def ejecutar_pruebas_itcosas_v1_pipeline(app):
    """

    Pipeline completo (itcosas v1):

      A) IOA (tmwgateway + varexp) -> Direcciones.csv

      B) SOE Local (Eventodiario + Direcciones.csv) -> SOE_Local.csv

      C) HIS (ODBC) multi-station opcional -> consolida en out/pruebas/data.csv

      D) SOE Monarch (empresa + checklist + SCADA + data.csv) -> SOE_Monarch.csv

      E) Checklist final (consolida) -> SOE_completo.xlsx



    A y C corren en paralelo. B espera A. D espera B y C. E espera D.

    """
    empresa = app.opcion_empresa_pyp.get() if hasattr(app, 'opcion_empresa_pyp') else None
    if not empresa or empresa == 'Empresa...':
        messagebox.showerror('Error', 'Selecciona la empresa.')
        return
    checklist = getattr(app, 'pyp_checklist_file', None)
    eventos = getattr(app, 'pyp_eventosdiario_file', None)
    varexp = getattr(app, 'pyp_varexp_file', None)
    tmw = getattr(app, 'pyp_tmwgateway_file', None)
    if not (checklist and os.path.isfile(checklist) and eventos and os.path.isfile(eventos) and varexp and os.path.isfile(varexp) and tmw and os.path.isfile(tmw)):
        messagebox.showerror('Faltan archivos', 'Debes seleccionar Checklist, EventosDiario, varexp y tmwgateway (itcosas v1).')
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
        _ui(app, lambda: app.console.write('>> No se detectaron estaciones en checklist. Paso HIS no se ejecutara.', 'warn'))
    env = app.secure_env()
    outdir = os.path.join(output_root(), 'out', 'pruebas')
    os.makedirs(outdir, exist_ok=True)
    runtime_root = _runtime_root()
    m = _mods()
    console = _console_factory(app)
    if getattr(app, 'console', None):
        app.console.clear()
    app.start_status('Iniciando pipeline (itcosas v1)...', indeterminate=True)
    console('>> Pipeline itcosas v1 - Inicio', 'info')
    for fname in ('Direcciones.csv', 'SOE_Local.csv', 'SOE_Monarch.csv', 'SOE_completo.xlsx', 'data.csv'):
        fpath = os.path.join(outdir, fname)
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass
    state = {'ioa': None, 'soe_local': None, 'his': None, 'his_done_count': 0, 'his_total': 1 if stations else 0, 'soe_monarch': None, 'checklist': None}
    artifacts = {'direcciones': os.path.join(outdir, 'Direcciones.csv'), 'soe_local': os.path.join(outdir, 'SOE_Local.csv'), 'his_data': os.path.join(outdir, 'data.csv'), 'soe_monarch': os.path.join(outdir, 'SOE_Monarch.csv'), 'soe_final': os.path.join(outdir, 'SOE_completo.xlsx')}

    def _station_arg(stations_list: list[str]) -> str:
        if not stations_list:
            return '%'
        return ','.join(stations_list)

    def _run_his(stations_list: list[str]):
        station_arg = _station_arg(stations_list)
        args = [m['his_soe'], empresa, '--station', station_arg, '--fecha', fecha, '--hora_inicio', hini, '--hora_fin', hfin, '--outdir', outdir]
        cmd = build_cmd(*args)
        label = station_arg if station_arg != '%' else 'todas'
        console(f">> CMD[HIS:{label}]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[HIS] '), on_done=lambda rc: _on_done_his(0 if rc == 0 else 1))

    def _on_done_his(code: int):
        state['his_done_count'] = state['his_total']
        if code == 0 and os.path.exists(artifacts['his_data']):
            state['his'] = 0
            _ui(app, lambda: app.success_status('HIS OK (consulta unica)'))
        elif code == 0:
            state['his'] = 1
            _ui(app, lambda: app.error_status('HIS completo pero no genero data.csv'))
        else:
            state['his'] = 1
            _ui(app, lambda: app.error_status('HIS fallo.'))
        _check_and_maybe_continue()

    def _run_ioa():
        cmd = build_cmd(m['ioa_v1'], f'--tmwgateway={tmw}', f'--varexp={varexp}', f'--outdir={outdir}')
        console(f">> CMD[IOA]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[IOA] '), on_done=lambda rc: _on_done_ioa(0 if rc == 0 else 1))

    def _on_done_ioa(code: int):
        state['ioa'] = code
        if code != 0:
            _ui(app, lambda: app.error_status('Paso IOA fallo.'))
            _check_and_maybe_continue()
            return
        _ui(app, lambda: app.success_status('Direcciones.csv generado (IOA)'))
        _run_soe_local()

    def _run_soe_local():
        cmd = build_cmd(m['soe_local_v1'], f'--eventos={eventos}', f"--direcciones={artifacts['direcciones']}", f'--outdir={outdir}')
        console(f">> CMD[SOE_LOCAL]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[SOE_LOCAL] '), on_done=lambda rc: _on_done_soe_local(0 if rc == 0 else 1))

    def _on_done_soe_local(code: int):
        state['soe_local'] = code
        if code != 0:
            _ui(app, lambda: app.error_status('Paso SOE Local fallo.'))
        else:
            _ui(app, lambda: app.success_status('SOE_Local.csv generado'))
        _check_and_maybe_continue()

    def _run_soe_monarch():
        scada_dir = os.path.join(output_root(), 'out', empresa, 'SCADA')
        faltantes = []
        for fname in ('32_10.csv', '10_4.csv', '19_1.csv'):
            if not os.path.isfile(os.path.join(scada_dir, fname)):
                faltantes.append(fname)
        if faltantes:
            msg = f'Faltan archivos SCADA en {scada_dir}:\n- ' + '\n- '.join(faltantes) + '\nActualiza SCADA antes de continuar.'
            messagebox.showerror('SCADA incompleto', msg)
            state['soe_monarch'] = 1
            _check_and_maybe_continue()
            return
        if not os.path.exists(artifacts['his_data']):
            messagebox.showerror('Falta data.csv (HIS)', 'No se encontro out/pruebas/data.csv.')
            state['soe_monarch'] = 1
            _check_and_maybe_continue()
            return
        cmd = build_cmd(m['soe_monarch_v1'], empresa, checklist, artifacts['his_data'])
        console(f">> CMD[SOE_MONARCH]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[SOE_MONARCH] '), on_done=lambda rc: _on_done_soe_monarch(0 if rc == 0 else 1))

    def _on_done_soe_monarch(code: int):
        state['soe_monarch'] = code
        if code == 0:
            _ui(app, lambda: app.success_status('SOE_Monarch.csv generado'))
            _run_checklist_final()
        else:
            _ui(app, lambda: app.error_status('SOE Monarch fallo.'))
            _check_and_maybe_continue()

    def _run_checklist_final(abrir_excel: bool=False):
        args = [f'--checklist={checklist}', f'--outdir={outdir}']
        if abrir_excel:
            args.append('--abrir-excel')
        cmd = build_cmd(m['checklist_v1'], *args)
        console(f">> CMD[CHECKLIST]: {' '.join(map(str, cmd))}", 'warn')
        app.tasks.run_subprocess(cmd, env=env, cwd=runtime_root, on_progress=_on_progress_factory(app, prefix='[CHECKLIST] '), on_done=lambda rc: _on_done_checklist(0 if rc == 0 else 1))

    def _on_done_checklist(code: int):
        state['checklist'] = code
        if code == 0:
            _ui(app, lambda: app.success_status('SOE_completo.xlsx generado'))
            _final_success_dialog()
        else:
            _ui(app, lambda: app.error_status('Checklist final fallo.'))
            _final_failure_dialog()

    def _check_and_maybe_continue():
        """

        Evalua las dependencias y dispara los pasos siguientes.

        - Lanza Monarch cuando SOE Local (B) y HIS(data.csv) (C) esten OK.

        - Lanza dialog final cuando Monarch + Checklist esten resueltos.

        """
        if state['soe_monarch'] is None:
            if state['soe_local'] == 0 and (state['his'] == 0 or state['his_total'] == 0):
                if state['his_total'] == 0:
                    messagebox.showerror('Faltan estaciones para HIS', 'No hay estaciones definidas (ni seleccionada ni en checklist). No se puede generar SOE Monarch.')
                    state['soe_monarch'] = 1
                else:
                    _run_soe_monarch()
        if state['soe_monarch'] in (0, 1) and state['checklist'] in (0, 1):
            if state['soe_monarch'] == 0 and state['checklist'] == 0:
                _final_success_dialog()
            else:
                _final_failure_dialog()

    def _final_success_dialog():
        files = []
        for k in ('direcciones', 'soe_local', 'his_data', 'soe_monarch', 'soe_final'):
            p = artifacts[k]
            if os.path.exists(p):
                files.append(p)
        if files:
            show_success_with_open(parent=app.ventana, mensaje='Pipeline completado con exito.', title='Pruebas PyP - itcosas v1', files=files)
        else:
            messagebox.showinfo('Pipeline completado', 'Proceso finalizado.', parent=app.ventana)

    def _final_failure_dialog():
        messagebox.showerror('Pipeline incompleto', 'Uno o mas pasos fallaron. Revisa la consola para mas detalles.', parent=app.ventana)
    _run_ioa()
    if stations:
        _run_his(stations)
    else:
        state['his'] = None
        state['his_total'] = 0

__all__ = ["ejecutar_pruebas_itcosas_v1_pipeline"]


