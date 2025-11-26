from __future__ import annotations

import os
from typing import List, Set, Tuple

from .common import build_cmd, load_workbook, messagebox, show_summary_dialog

def ejecutar_validacion_hsh(app):
    """

    Valida HSH usando el nuevo esquema de importacion:

    - Importa SCADA + HSH con importar_all y usecase=hsh_validar (incluye dump remoto SCADA especifico).

    - Soporta flex (empresa relacionada) automaticamente va --flex.

    - Convierte SCADA/HSH de empresa principal (y respaldo si aplica).

    - Ejecuta scripts.validaciones_hsh al final.

    """

    empresa = app.opcion_empresa_hsh_validar.get()

    dominio = "CC"

    if not empresa or empresa == "Empresa...":

        messagebox.showerror("Error", "Selecciona una empresa.")

        return

    # Empresa relacionada (respaldo) si aplica

    respaldo_map = {"ITCO": "TRA", "TRA": "ITCO",
                    "REPS": "REPP", "REPP": "REPS"}

    respaldo = respaldo_map.get(empresa.upper())

    btn = app.boton_validar_hsh

    btn.config(text=" Validando... ", state="disabled")

    mod_importar = "scripts.importar_all"

    mod_convertir = "scripts.Convertir_all"   # usa --only sca / --only hsh

    mod_validar = "scripts.validaciones_hsh"

    env = app.secure_env()

    cwd = app.base_dir  # validaciones_hsh espera 'out/' relativo al CWD

    app.start_status("Preparando validacion HSH", indeterminate=True)

    # --- helpers UI/log ---

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

    def _collect_validation_counts(xlsx_path: str) -> Tuple[int, int]:

        if load_workbook is None or not os.path.exists(xlsx_path):

            return (0, 0)

        try:

            wb = load_workbook(xlsx_path, read_only=True, data_only=True)

        except Exception:

            return (0, 0)

        try:

            header_row = next(
                wb.active.iter_rows(min_row=1, max_row=1, values_only=True))

        except StopIteration:

            wb.close()

            return (0, 0)

        headers = [str(value or "").strip().lower() for value in header_row]

        header_map = {name: idx for idx, name in enumerate(headers) if name}

        key_idx = header_map.get("key")

        etiqueta_idx = header_map.get("etiqueta")

        all_keys: Set[str] = set()

        invalid_keys: Set[str] = set()

        for row_number, row in enumerate(wb.active.iter_rows(min_row=2, values_only=True), start=2):

            if not row:

                continue

            key_value = ""

            if key_idx is not None and key_idx < len(row):

                key_value = str(row[key_idx] or "").strip()

            if not key_value:

                key_value = f"ROW#{row_number}"

            etiqueta_value = ""

            if etiqueta_idx is not None and etiqueta_idx < len(row):

                etiqueta_value = str(row[etiqueta_idx] or
                                     "").strip().upper()

            all_keys.add(key_value)

            if etiqueta_value in {"ERROR", "CRITICAL"}:

                invalid_keys.add(key_value)

        wb.close()

        total_keys = len(all_keys)

        invalid_count = len(invalid_keys)

        valid_count = max(total_keys - invalid_count, 0)

        return valid_count, invalid_count

    def _fin(rc: int):

        def _end():

            btn.config(text=" Validar ", state="normal")

            if rc == 0:

                out_dir = os.path.join(
                    app.base_dir, "out", f"Validaciones_{empresa}")

                nombre_archivo = os.path.join(
                    out_dir, f"Validaciones_{empresa}.xlsx")

                app.success_status("Validacion lista")

                archivos_resultado: List[str] = []

                if os.path.exists(out_dir):

                    for archivo in os.listdir(out_dir):

                        if archivo.endswith('.xlsx') and 'Validacion' in archivo:

                            archivos_resultado.append(
                                os.path.join(out_dir, archivo))

                if not archivos_resultado and os.path.exists(nombre_archivo):

                    archivos_resultado = [nombre_archivo]

                validados, fallidos = _collect_validation_counts(nombre_archivo)

                resumen = f"Unifilares validados: {validados}\nUnifilares con alertas: {fallidos}"

                detalles: List[str] = [
                    f"Empresa: {empresa}",
                ]

                if respaldo:

                    detalles.append(f"Respaldo: {respaldo}")

                detalles.append(f"Directorio: {out_dir}")

                if not archivos_resultado:

                    detalles.append(
                        "No se encontraron archivos de salida en la validacion.")

                show_summary_dialog(

                    parent=app.ventana,

                    mensaje=resumen,

                    title="Validacion HSH lista",

                    status="success",

                    details=detalles,

                    files=archivos_resultado or None,

                    show_open_file=bool(archivos_resultado),

                )

            else:

                error_msg = "La validacion termino con errores."

                app.error_status(error_msg)

                show_summary_dialog(

                    parent=app.ventana,

                    mensaje=error_msg,

                    title="Validacion HSH con errores",

                    status="error",

                    details=[error_msg],

                )

        _ui(_end)

    # Limpia consola y anuncia inicio

    if getattr(app, "console", None):

        app.console.clear()

    _console(">> Consola lista (Validacion HSH)", "info")

    # El checkbox decide si hay que refrescar DB (importar + convertir) o correr local

    needs_update = bool(getattr(app, "checkbox_var_hsh", None)
                        and app.checkbox_var_hsh.get())

    # ---- Ruta local (sin actualizacion): solo correr validaciones ----

    if not needs_update:

        _ui(lambda: app.set_status("Validando HSH modo local"))

        if respaldo:
            cmd = build_cmd(mod_validar, empresa, "--respaldo", respaldo)
        else:
            cmd = build_cmd(mod_validar, empresa)

        _console(f">> CMD[VALIDAR]: {' '.join(map(str, cmd))}", "warn")

        app.tasks.run_subprocess(

            cmd,

            env=env,

            cwd=cwd,

            on_progress=_on_progress_pref("VALIDAR"),

            on_done=_fin

        )

        return

    # ===== Ruta CON actualizacion =====

    servidor_principal = app.generar_server(empresa, dominio)

    if not servidor_principal:

        btn.config(text=" Validar ", state="normal")

        app.error_status("No se pudo resolver el servidor")

        messagebox.showerror(
            "Error", "No se pudo resolver el servidor para la empresa o dominio.")

        return

    servidor_respaldo = app.generar_server(respaldo, dominio) if respaldo else None
    if respaldo and not servidor_respaldo:
        btn.config(text=" Validar ", state="normal")
        app.error_status(f"No se pudo resolver el servidor respaldo para {respaldo}.")
        messagebox.showerror("Error", f"No se pudo resolver el servidor respaldo para {respaldo}.")
        return

    cmd_import_principal = build_cmd(
        mod_importar,
        servidor_principal,
        empresa,
        "sca,hsh",
        "--usecase", "hsh_validar",
    )
    cmd_import_respaldo = (
        build_cmd(mod_importar, servidor_respaldo, respaldo, "sca,hsh", "--usecase", "hsh_validar")
        if respaldo and servidor_respaldo else None
    )

    # Converts empresa principal (granulares con --only)

    cmd_conv_sca = build_cmd(mod_convertir, empresa,
                             "Validar_HSH", "--only", "sca")

    cmd_conv_hsh = build_cmd(mod_convertir, empresa,
                             "Validar_HSH", "--only", "hsh")

    _console(
        f">> CMD[CONVERT-SCADA]: {' '.join(map(str, cmd_conv_sca))}", "warn")

    _console(
        f">> CMD[CONVERT-HSH]: {' '.join(map(str, cmd_conv_hsh))}", "warn")

    # Si hay respaldo definido agregamos conversiones explícitas de respaldo.

    if respaldo:

        cmd_conv_sca_res = build_cmd(
            mod_convertir, respaldo, "Validar_HSH", "--only", "sca")

        cmd_conv_hsh_res = build_cmd(
            mod_convertir, respaldo, "Validar_HSH", "--only", "hsh")

        _console(
            f">> CMD[CONVERT-SCADA-RES]: {' '.join(map(str, cmd_conv_sca_res))}", "warn")

        _console(
            f">> CMD[CONVERT-HSH-RES]: {' '.join(map(str, cmd_conv_hsh_res))}", "warn")

    else:

        cmd_conv_sca_res = None

        cmd_conv_hsh_res = None

    # Estado extendido

    state = {

        "import": {
            "principal": None,
            "respaldo": None if respaldo else 0,
        },

        "convert": {

            "sca": None,

            "hsh": None,

            "sca_res": None if respaldo else 0,

            "hsh_res": None if respaldo else 0,
        },

    }

    def _try_run_validaciones():
        import_vals = list(state["import"].values())
        if any(v is None for v in import_vals):
            return
        if any(v != 0 for v in import_vals):
            return

        conv_vals = list(state["convert"].values())

        if all(v == 0 for v in conv_vals):

            _ui(lambda: app.set_status("Validando HSH"))

            if respaldo:
                cmd_val = build_cmd(mod_validar, empresa,
                                    "--respaldo", respaldo)
            else:
                cmd_val = build_cmd(mod_validar, empresa)

            _console(f">> CMD[VALIDAR]: {' '.join(map(str, cmd_val))}", "warn")

            app.tasks.run_subprocess(

                cmd_val,

                env=env,

                cwd=cwd,

                on_progress=_on_progress_pref("VALIDAR"),

                on_done=_fin

            )

        elif all(v is not None for v in conv_vals) and any(v == 1 for v in conv_vals):

            # Alguna conversion fall

            _ui(lambda: app.error_status(
                "Una conversion fallo (principal o respaldo). Revisa la consola."))

            _ui(lambda: btn.config(text=" Validar ", state="normal"))

    def _after_principal_scada():

        # Si hay respaldo y an no lanzamos su conversion SCADA

        if respaldo and state["convert"]["sca_res"] is None and cmd_conv_sca_res:

            _ui(lambda: app.set_status(
                f"Convirtiendo SCADA respaldo {respaldo}"))

            app.tasks.run_subprocess(

                cmd_conv_sca_res,

                resource_key=f"{respaldo}:convert:validar_hsh:scada",

                env=env,

                cwd=cwd,

                on_progress=_on_progress_pref("CONVERT-SCADA-RES"),

                on_done=lambda rc2: (

                    state["convert"].__setitem__(
                        "sca_res", 0 if rc2 == 0 else 1),

                    _try_run_validaciones()

                )

            )

        else:

            _try_run_validaciones()

    def _after_principal_hsh():

        if respaldo and state["convert"]["hsh_res"] is None and cmd_conv_hsh_res:

            _ui(lambda: app.set_status(
                f"Convirtiendo HSH respaldo {respaldo}"))

            app.tasks.run_subprocess(

                cmd_conv_hsh_res,

                resource_key=f"{respaldo}:convert:validar_hsh:hsh",

                env=env,

                cwd=cwd,

                on_progress=_on_progress_pref("CONVERT-HSH-RES"),

                on_done=lambda rc2: (

                    state["convert"].__setitem__(
                        "hsh_res", 0 if rc2 == 0 else 1),

                    _try_run_validaciones()

                )

            )

        else:

            _try_run_validaciones()

    def _start_conversions_after_import():
        if state["import"]["principal"] is None:
            state["import"]["principal"] = 0
        if state["import"]["respaldo"] is None:
            state["import"]["respaldo"] = 0

        # Lanzamos conversiones de la empresa principal en paralelo

        _ui(lambda: app.set_status("Convirtiendo SCADA principal"))

        app.tasks.run_subprocess(

            cmd_conv_sca,

            resource_key=f"{empresa}:convert:validar_hsh:scada",

            env=env,

            cwd=cwd,

            on_progress=_on_progress_pref("CONVERT-SCADA"),

            on_done=lambda rc2: (

                state["convert"].__setitem__("sca", 0 if rc2 == 0 else 1),

                _after_principal_scada()

            )

        )

        _ui(lambda: app.set_status("Convirtiendo HSH principal"))

        app.tasks.run_subprocess(

            cmd_conv_hsh,

            resource_key=f"{empresa}:convert:validar_hsh:hsh",

            env=env,

            cwd=cwd,

            on_progress=_on_progress_pref("CONVERT-HSH"),

            on_done=lambda rc2: (

                state["convert"].__setitem__("hsh", 0 if rc2 == 0 else 1),

                _after_principal_hsh()

            )

        )

    def _after_import_res(rc: int):
        state["import"]["respaldo"] = rc
        if rc != 0:
            _ui(lambda: app.error_status("Importacion (SCADA+HSH) respaldo fallo. Revisa la consola."))
            _ui(lambda: btn.config(text=" Validar ", state="normal"))
            return
        _start_conversions_after_import()

    def _run_import_res():
        if not cmd_import_respaldo:
            state["import"]["respaldo"] = 0
            _start_conversions_after_import()
            return
        _ui(lambda: app.set_status(f"Sincronizando hsh_validar respaldo ({respaldo})..."))
        _console(f">> CMD[IMPORT respaldo]: {' '.join(map(str, cmd_import_respaldo))}", "warn")
        app.tasks.run_subprocess(
            cmd_import_respaldo,
            resource_key=f"{respaldo}:import:sca+hsh:hsh_validar",
            env=env,
            cwd=cwd,
            on_progress=_on_progress_pref("IMPORT (SCA+HSH)"),
            on_done=_after_import_res,
        )

    def _after_import_principal(rc: int):
        state["import"]["principal"] = rc
        if rc != 0:
            _ui(lambda: app.error_status("Importacion (SCADA+HSH) principal fallo. Revisa la consola."))
            _ui(lambda: btn.config(text=" Validar ", state="normal"))
            return
        if cmd_import_respaldo:
            _run_import_res()
        else:
            state["import"]["respaldo"] = 0
            _start_conversions_after_import()

    _ui(lambda: app.set_status("Sincronizando hsh_validar (SCADA+HSH)..."))
    _console(f">> CMD[IMPORT principal]: {' '.join(map(str, cmd_import_principal))}", "warn")
    app.tasks.run_subprocess(
        cmd_import_principal,
        resource_key=f"{empresa}:import:sca+hsh:hsh_validar",
        env=env,
        cwd=cwd,
        on_progress=_on_progress_pref("IMPORT (SCA+HSH)"),
        on_done=_after_import_principal,
    )

__all__ = ["ejecutar_validacion_hsh"]
