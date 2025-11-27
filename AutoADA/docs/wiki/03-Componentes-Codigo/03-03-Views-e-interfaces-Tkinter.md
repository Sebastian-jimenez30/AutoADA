# 03-03 – Views e interfaces Tkinter

En esta página se describen las vistas y componentes visuales de AutoADA, incluyendo cómo se estructuran los formularios y cómo se recomienda extender la IU.

---

## Base de vistas y tema

### `ui/base_view.py`

- Clase `BaseView` (hereda de `ttk.Frame`):
  - Configura un `Frame` con estilo `App.TFrame`.
  - Métodos:
    - `center_box(padx, pady)`: crea un frame centrado dentro de la vista para colocar contenido.
    - `add_title(parent, text, style, pady)`: añade un título con estilo consistente.
    - `set_size(width, height)`: fija tamaño inicial de ventana y la centra en pantalla.

Uso recomendado:

- Cada vista en `interfaces/` suele crear una instancia de `BaseView` o heredar su comportamiento para mantener consistencia.

### `ui/theme.py`

- Define:
  - Colores corporativos (PRIMARY, BACKGROUND, etc.).
  - Fuentes base y de títulos.
  - Espaciados estándar (`SPACING_XS`, `SPACING_M`, etc.).
- Registra estilos `App.*`:
  - Frames (`App.TFrame`, `App.Surface.TFrame`, `App.Sidebar.TFrame`).
  - Labels (`App.TLabel`, `App.Muted.TLabel`, `App.Title.TLabel`, etc.).
  - Botones (`App.TButton`, `App.Sidebar.TButton`, `App.SidebarActive.TButton`).
  - Entradas (`App.TEntry`, `App.TCombobox`).

Esto centraliza el look&feel y facilita cambios globales de estilo.

---

## Componentes UI reutilizables (`ui/components/`)

### Navbar (`navbar.py`)

- Implementa un sidebar con:
  - Logo.
  - Botón Inicio.
  - Secciones plegables (Buscar, HSH, Jobs, Unifilares, PyP, Consultar).
- Administra:
  - Estado de opción activa.
  - Scroll interno cuando hay muchas opciones.
  - Callbacks para notificar al `AppController` de las selecciones.

### Consola (`console.py`)

- Clase `LogConsole`:
  - Área de texto de solo lectura con colores para info/warn/error.
  - Scrollbar vertical.
  - Botón `Detener` integrado para detener procesos en curso (si el controller define handler).
  - API:
    - `write(line, tag)`, `clear()`.
    - `set_autoscroll(bool)`.
    - `set_stop_handler(callback)`, `set_stop_enabled(bool)`.

Usada por casi todas las vistas operativas para mostrar stdout de scripts.

### StatusBar (`statusbar.py`)

- Muestra:
  - Mensaje de estado.
  - Barra de progreso indeterminada o determinada.
- Métodos:
  - `start(msg, indeterminate=True)`.
  - `set(msg)`, `success(msg)`, `error(msg)`, `stop()`.
  - `progress(value, maximum)` para uso determinate.

Se sitúa en la parte inferior de la ventana principal y se controla desde `AppController`.

### Diálogos de éxito y resúmenes (`success_dialog.py`, `dialogs.py`)

- `show_success_with_open(...)` y `show_summary_dialog(...)`:
  - Muestran mensajes de éxito/resultado.
  - Listan archivos generados.
  - Ofrecen botones:
    - Abrir archivo.
    - Mostrar carpeta.
    - Copiar ruta.

Estos diálogos mejoran significativamente la experiencia tras un pipeline.

---

## Vistas funcionales (`interfaces/*.py`)

Cada archivo en `interfaces/` define una vista para un caso de uso:

- `marco_bienvenida.py`:
  - Muestra estado de datos (última actualización SCADA/HSH/ODSTXT).
  - Ofrece botones para actualizar datos y refrescar estado.
- `marco_buscar_key.py`:
  - Pantallas para buscar keys de forma manual o a partir de Excel.
  - Integra consola, combobox de empresa, checkbox “Actualizar BD”.
- `marco_hsh.py`:
  - Vistas para crear/validar/cambiar/eliminar tags HSH.
  - Campos para seleccionar archivos de entrada, opciones de empresa/dominio, checkboxes para actualizar BD.
- `marco_jobs.py`:
  - Vistas para crear, eliminar y cambiar nombre de señales.
  - Formularios orientados a Excel de entrada y opciones por empresa.
- `marco_unifilares.py`:
  - Campos para importar/convertir ODS/SCADA y seleccionar archivos de unifilares.
- `marco_pruebas_pyp.py`:
  - Pestañas para PyP v1 y v2.
  - Selección de empresa, fecha/hora, archivos checklist/eventos/etc.
- `marco_consultar.py`:
  - Vista para consultar RTU/SAS.
  - Selector de empresa y lista de RTU/SAS disponible.

Cada vista:

- Declara variables `StringVar`/`BooleanVar` según sea necesario.
- Configura bindings a handlers del `AppController`.
- Compartimenta la consola y la status bar según las necesidades del módulo.

---

## Patrón recomendado para nuevas vistas

Para agregar un nuevo módulo funcional:

1. Crear un archivo en `interfaces/` (por ejemplo, `marco_nuevo_modulo.py`).
2. Definir una función factory (por ejemplo, `crear_marco_nuevo_modulo(app)`) que:
   - Cree un `BaseView` asociado al `app.content`.
   - Cree un “box” centrado con `center_box`.
   - Configure la UI (labels, entradas, botones, consola, etc.).
   - Guarde referencias relevantes en `app` si se necesitan (botones, rutas de archivo).
3. Registrar la vista en `AppController._register_frames()` o en el callback de menú:
   - `self.router.register("nuevo_modulo", lambda: crear_marco_nuevo_modulo(self))`.
4. Añadir una opción correspondiente en el navbar (`ui/components/navbar.py`) con la clave adecuada.

Este patrón mantiene la UI organizada y hace que añadir casos de uso sea incremental y predecible.

---

## Resumen

- `BaseView` y `theme` proporcionan una base visual coherente.
- `ui/components` ofrece bloques reutilizables con comportamientos bien definidos.
- `interfaces/*.py` encapsulan la lógica de presentación por caso de uso.
- La combinación de todo esto permite una UI consistente, extensible y separada de la lógica de negocio/orquestación.

