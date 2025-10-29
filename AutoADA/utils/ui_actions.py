import tkinter as tk
from tkinter import filedialog, ttk
from util import verificar_habilitar_boton  


def seleccionar_archivo(app,
                        boton_seleccionar_archivo,
                        opcion_empresa: tk.StringVar,
                        opcion_dominio: tk.StringVar,
                        boton_accion: ttk.Button,
                        valor_defecto_boton="Seleccionar archivo",
                        tipo=None):
    """
    Extraído desde el main original. La interfaz sigue llamando a app.seleccionar_archivo(...),
    pero AppController solo delega a este helper.
    """
    if tipo == "unifilares":
        archivos = filedialog.askopenfilenames(
            title="Seleccionar archivos",
            filetypes=[("Archivos TXT", "*.txt;*.TXT")]
        )
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
        return

    # Excel / otros
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
        elif tipo == "cambiar_nombre":                           
            app.archivo_cambiar_nombre = archivo               
    else:
        boton_seleccionar_archivo.config(text=valor_defecto_boton)
        if tipo == "buscar_keys":
            app.archivo_excel_buscar_keys = None
        elif tipo == "crear_senales":
            app.archivo_crear_senales = None
        elif tipo == "eliminar_senales":
            app.archivo_eliminar_senales = None

    verificar_habilitar_boton(
        opcion_empresa, opcion_dominio,
        boton_seleccionar_archivo, boton_accion,
        valor_defecto_boton
    )


def mostrar_boton_seleccionar_archivo_unifilares(app):
    """
    Conserva el comportamiento que las interfaces esperan (nombres de attrs, grid/pack…).
    """
    # crea botones si no existen
    if getattr(app, "boton_seleccionar_archivo_unifilares", None) is None:
        parent = getattr(app, "marco_hsh_validar", app.ventana)
        app.boton_seleccionar_archivo_unifilares = ttk.Button(
            parent,
            text="Seleccionar archivo",
            command=lambda: seleccionar_archivo(
                app,
                app.boton_seleccionar_archivo_unifilares,
                app.opcion_empresa_unifilares,
                app.opcion_dominio_unifilares,
                app.boton_ejecutar_unifilares,
                valor_defecto_boton="Seleccionar archivo",
                tipo="unifilares"
            )
        )
        try:
            app.boton_seleccionar_archivo_unifilares.grid(row=2, column=0, pady=10, columnspan=2)
        except Exception:
            app.boton_seleccionar_archivo_unifilares.pack(pady=10)

    if getattr(app, "boton_ejecutar_unifilares", None) is None:
        parent = getattr(app, "marco_hsh_validar", app.ventana)
        app.boton_ejecutar_unifilares = ttk.Button(
            parent,
            text="Ejecutar",
            state="disabled",
            command=getattr(app, "ejecutar_script_unifilares", lambda: None)
        )
        try:
            app.boton_ejecutar_unifilares.grid(row=4, column=0, columnspan=2, pady=10)
        except Exception:
            app.boton_ejecutar_unifilares.pack(pady=10)

    # Lógica de habilitación (incluye checkbox)
    def _habilitar(*_):
        empresa_ok = app.opcion_empresa_unifilares.get() != "Empresa..."
        checkbox = app.checkbox_var_unifilares.get() if hasattr(app, 'checkbox_var_unifilares') else False
        if not checkbox and empresa_ok:
            app.boton_ejecutar_unifilares.config(state="normal")
            return
        archivos_ok = bool(getattr(app, 'archivos_unifilares', None))
        dominio_ok = app.opcion_dominio_unifilares.get() != "Dominio..."
        app.boton_ejecutar_unifilares.config(
            state="normal" if (empresa_ok and dominio_ok and archivos_ok) else "disabled"
        )

    # Vincular cambios
    try:
        app.opcion_empresa_unifilares.trace_add("write", _habilitar)
        app.opcion_dominio_unifilares.trace_add("write", _habilitar)
        if hasattr(app, 'checkbox_var_unifilares'):
            app.checkbox_var_unifilares.trace_add("write", _habilitar)
    except Exception:
        pass

def seleccionar_archivo_simple(title="Seleccionar archivo",
                               extensions=None,
                               multiple=False,
                               initialdir=None):
    """
    Selector de archivos simple y genérico.
    - title: título de la ventana.
    - extensions: lista de tuplas [("Excel/CSV", "*.xlsx *.xls *.csv"), ("Todos", "*.*")]
    - multiple: si True, devuelve tuple de rutas; si False, str o "" si cancelado.
    - initialdir: carpeta inicial (opcional).
    """
    filetypes = extensions or [("Todos", "*.*")]

    if multiple:
        paths = filedialog.askopenfilenames(
            title=title,
            filetypes=filetypes,
            initialdir=initialdir or None
        )
        return paths  # tuple (puede estar vacío)
    else:
        path = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes,
            initialdir=initialdir or None
        )
        return path 