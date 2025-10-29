import os
import sys
import subprocess

def verificar_habilitar_boton(opcion_empresa, opcion_dominio, cadena, boton, valor_defecto_boton="Seleccionar archivo", checkbox=None):
    empresa_ok = opcion_empresa.get() != "Empresa..."
    dominio_ok = opcion_dominio.get() != "Dominio..."
    texto_ok = hasattr(cadena, "get") and cadena.get() or hasattr(cadena, "cget") and cadena.cget("text") != valor_defecto_boton

    if checkbox is not None and checkbox.get():
        boton.config(state="normal" if empresa_ok and dominio_ok and texto_ok else "disabled")
    else:
        boton.config(state="normal" if empresa_ok and texto_ok else "disabled")


def ejecutar_script(script_path, *args, timeout=None):
    """
    Versión síncrona de conveniencia (si aún la usas en algún lado).
    Para concurrencia real, usa TaskRunner.run_subprocess en los handlers.
    """
    cmd = [sys.executable, script_path] + list(args)
    try:
        resultado = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        if resultado.returncode != 0:
            raise RuntimeError(f"Error al ejecutar {os.path.basename(script_path)}:\n{resultado.stdout}\n{resultado.stderr}")
    except Exception as e:
        raise RuntimeError(f"Error al ejecutar {os.path.basename(script_path)}: {e}")


def limpiar_marco(marco):
    for widget in marco.winfo_children():
        widget.destroy()


def seleccionar_archivo(app, boton_seleccionar_archivo, opcion_empresa, opcion_dominio, boton_accion, valor_defecto_boton="Seleccionar archivo", tipo=None):
    from tkinter import filedialog

    if tipo == "unifilares":
        archivos = filedialog.askopenfilenames(title="Seleccionar archivos", filetypes=[("Archivos TXT", "*.txt;*.TXT")])
        if archivos:
            app.archivos_unifilares = archivos
            boton_seleccionar_archivo.config(text="Archivos seleccionados")
        else:
            app.archivos_unifilares = None
            boton_seleccionar_archivo.config(text=valor_defecto_boton)

        habilitar = (
            opcion_empresa.get() != "Empresa..."
            and opcion_dominio.get() != "Dominio..."
            and app.archivos_unifilares
        )
        boton_accion.config(state="normal" if habilitar else "disabled")

    else:
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[("Archivos Excel", "*.xlsx"), ("Todos los archivos", "*.*")]
        )
        if archivo:
            boton_seleccionar_archivo.config(text="Archivo seleccionado")
            if tipo == "buscar_keys":
                app.archivo_excel_buscar_keys = archivo
            elif tipo == "crear_senales":
                app.archivo_crear_senales = archivo
            elif tipo == "eliminar_senales":
                app.archivo_eliminar_senales = archivo
        else:
            boton_seleccionar_archivo.config(text=valor_defecto_boton)
            if tipo == "buscar_keys":
                app.archivo_excel_buscar_keys = None
            elif tipo == "crear_senales":
                app.archivo_crear_senales = None
            elif tipo == "eliminar_senales":
                app.archivo_eliminar_senales = None

        verificar_habilitar_boton(opcion_empresa, opcion_dominio, boton_seleccionar_archivo, boton_accion, valor_defecto_boton)