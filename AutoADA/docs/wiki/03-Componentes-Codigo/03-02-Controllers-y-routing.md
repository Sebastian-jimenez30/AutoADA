# 03-02 – Controllers y routing

Esta página se centra en el núcleo de la aplicación GUI: `AppController` y `FrameRouter`, responsables de orquestar la ventana principal, la navegación y el estado global.

---

## `AppController` (controllers/app_controller.py)

`AppController` es la clase que coordina la mayoría de funciones de alto nivel de la GUI.

### Responsabilidades principales

1. **Configurar la ventana y el layout**
   - Ajustar título y fondo de la ventana Tk.
   - Crear el contenedor principal con:
     - Sidebar (navbar) en la izquierda.
     - Área de contenido central (vistas).
     - Barra de estado en la parte inferior.

2. **Inicializar servicios y estado**
   - Crear `AppState` con usuario, rol y ubicación.
   - Inicializar `SecurityService` y `ServerResolver`.
   - Resolver mapas de empresas y dominios para la UI.

3. **Gestionar el entorno de trabajo**
   - Llamar a `ensure_workdirs()` para asegurar `db/`, `tls/`, `out/`, `log/`.
   - Guardar `base_dir` para pasarlo como `cwd` a scripts.
   - Cargar el vault y convertirlo en variables de entorno con `secure_env()`.

4. **Navegación y vistas**
   - Crear un `FrameRouter`.
   - Registrar vistas (por ejemplo, la de bienvenida) en `_register_frames()`.
   - Responder a selecciones del navbar (`_on_menu_select`) creando y mostrando vistas según la opción elegida.

5. **Tareas asíncronas y estado visual**
   - Poseer una instancia de `TaskRunner`.
   - Escuchar cambios de estado de `TaskRunner` (`_on_task_runner_state`).
   - Actualizar:
     - La barra de estado (iniciar/terminar progreso).
     - El botón “Detener” de la consola embebida.

6. **Servicios auxiliares**
   - Métodos como:
     - `set_status`, `start_status`, `success_status`, `error_status`, `stop_status`.
     - `generar_server(empresa, dominio)` usando `ServerResolver`.
     - `obtener_empresas_permitidas()` y `obtener_empresas_jobs()` usando `SecurityService`.
     - `seleccionar_archivo(...)` y `mostrar_boton_seleccionar_archivo_unifilares()` delegando en `utils.ui_actions`.

---

### Gestión de vistas y widgets

`AppController` mantiene referencias a:

- Vista/vista actual (`marco_actual`).
- Consola (`console`) y barra de estado (`statusbar`).
- Botones y variables de estado específicos de cada módulo (por ejemplo, rutas de archivos seleccionados, opciones de combos).

Cuando se cambia de vista:

- Se destruye el marco anterior (si existe).
- Se construye el nuevo marco vía `FrameRouter`.
- Se inserta en el contenedor central.

Este patrón permite que cada vista se implemente en su propio archivo en `interfaces/` sin acoplarse fuertemente al resto de la UI.

---

## `FrameRouter` (controllers/frame_router.py)

Clase simple pero útil para modularizar la creación de vistas.

### Concepto

- Mantiene un registro `key → factory`.
- Una “factory” es una función sin argumentos que devuelve una instancia de vista (por ejemplo, una clase que hereda de `BaseView`).

### Uso típico

- En `AppController._register_frames()`:
  - `self.router.register("bienvenida", lambda: crear_marco_bienvenida(self))`
  - (y de forma similar para otras vistas, cuando se extiende la app).
- Al seleccionar una opción en el navbar:
  - `FrameRouter.build(key)` se invoca con la clave correspondiente.
  - Si la clave no está registrada, se lanza un error claro (“Vista no registrada”).

Esto desacopla:

- La lógica de navegación (`AppController`).
- La construcción concreta de vistas (`interfaces/*.py`).

---

## Integración con el navbar

El navbar (`ui/components/navbar.py`) se construye con:

- Un mapa de grupos y opciones.
- Un callback de selección que recibe:
  - Grupo.
  - Nombre de la opción.
  - Un valor entero asociado.

`AppController._setup_menu()`:

- Crea el navbar.
- Define el callback `on_select` para:
  - Traducir la selección del menú a una clave interna de vista.
  - Llamar a `mostrar_marco(...)` con la vista apropiada construida por el `FrameRouter`.

De esta forma, el controlador actúa como **puente** entre la representación visual del menú y las vistas concretas que el usuario ve.

---

## Control de ubicación / seguridad al nivel de controller

`AppController._guard_location()`:

- Usa `SecurityService` para determinar la ubicación (ITCO/REP/Desconocido).
- Ajusta:
  - Las empresas disponibles en menús.
  - Comportamientos específicos de ciertos módulos, si aplica.
- Puede abortar la ejecución si la ubicación no está autorizada.

Esto asegura que la lógica de “dónde se puede usar AutoADA” se centralice en el controlador y los servicios, y no se repita en cada vista.

---

## Resumen

- `AppController` es el **centro de coordinación** entre UI, servicios, entorno y ejecución de tareas.
- `FrameRouter` mantiene la creación de vistas desacoplada del controlador.
- El navbar se conecta con ambos para administrar navegación de forma clara y extensible.

Comprender estos componentes es clave antes de agregar nuevas vistas o modificar el comportamiento global de la aplicación.

