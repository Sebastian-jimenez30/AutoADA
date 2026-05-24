# 02-01 – Vista de capas

Esta página presenta la **arquitectura por capas** de AutomatizADA. El objetivo es tener una visión clara de qué hace cada parte y cómo se relacionan entre sí.

---

## Diagrama conceptual de capas

En términos conceptuales, la arquitectura puede verse así:

> **UI (Tkinter/ttk)**  
> → **Controlador de aplicación (AppController)**  
> → **Handlers (orquestación de casos de uso)**  
> → **Scripts CLI (lógica pesada y acceso a datos externos)**  
> → **Sistemas/recursos externos (SCADA, HSH, ODS/HIS, RTU/SAS, archivos, servicios)**  

Soportado transversalmente por:

- **Servicios** (seguridad, resolución de servidores).
- **Utilidades** (rutas, ejecución asíncrona, verificaciones, helpers de UI).
- **Configuración y plantillas** (JSON, Excel, assets).

---

## Capa de interfaz de usuario (UI)

Directorio principal: `interfaces/` y `ui/`.

- **Vistas Tkinter** (`interfaces/*.py`):
  - Una vista por caso de uso (bienvenida, buscar keys, HSH, jobs, unifilares, PyP, consultar RTU).
  - Cada vista define formularios, combos, checkboxes, botones y una consola embebida.
- **Base y tema**:
  - `ui/base_view.py`: clase base para vistas, con helpers para centrar contenido y fijar tamaño.
  - `ui/theme.py`: define paleta de colores, tipografías y estilos `App.*` compartidos.
- **Componentes reutilizables** (`ui/components/`):
  - `navbar.py`: menú lateral con secciones plegables y opción Inicio.
  - `console.py`: consola embebida (`LogConsole`) con colores y botón Detener.
  - `statusbar.py`: barra de estado con mensajes y barra de progreso.
  - `success_dialog.py`: diálogos enriquecidos para mostrar archivos generados.
  - Otros: inputs, date/time pickers, diálogos auxiliares.

Responsabilidad principal: ofrecer una **experiencia consistente** para usuarios operativos, ocultando detalles de línea de comandos.

---

## Capa de controlador de aplicación

Archivo principal: `controllers/app_controller.py`.

Responsabilidades:

- Crear y organizar el **layout principal**:
  - Sidebar (navbar) a la izquierda.
  - Área de contenido central donde se montan las vistas.
  - Barra de estado en la parte inferior.
- Mantener el **estado global** del usuario y contexto:
  - Usuario, rol, ubicación (ITCO/REP/Desconocido).
  - Empresa/dominio activos según selección.
- Coordinar la **navegación**:
  - Usa `FrameRouter` para registrar y construir vistas bajo demanda.
  - Interpreta las selecciones del navbar y monta la vista correspondiente.
- Gestionar **tareas asíncronas**:
  - Posee una instancia de `TaskRunner`.
  - Reacciona a cambios de estado (tareas en ejecución o no) para actualizar la UI (status bar, botón Detener).
- Gestionar el **entorno seguro**:
  - Consume el vault desencriptado.
  - Pobla variables de entorno (MONGO_*, SSH_*, ODBC_*, TLS_*, etc.) antes de lanzar scripts.
  - Controla qué empresas y dominios se muestran según ubicación.

En resumen, es el “cerebro” que conecta la UI con las capas inferiores.

---

## Capa de ruteo de vistas

Archivo: `controllers/frame_router.py`.

Rol:

- Proporcionar un **registro simple** de vistas (`key → factory`).
- Construir instancias de vistas cuando el controlador lo solicita.

Aunque es pequeña, esta capa permite desacoplar la navegación de la creación concreta de cada vista.

---

## Capa de servicios

Directorio: `services/`.

Servicios principales:

- `SecurityService`:
  - Detecta la ubicación (ITCO/REP/Desconocido) a partir del hostname.
  - Determina qué empresas están permitidas y qué vault debe usarse.
- `ServerResolver`:
  - Lee configuraciones (`config/servers.json`).
  - Mapea claves de empresa/dominio a hostnames concretos.
  - Expone vistas de solo lectura usadas por la UI (combos) y los handlers.

Estos servicios encapsulan lógica transversal de **seguridad** y **topología de servidores**, evitando duplicaciones en la UI o scripts.

---

## Capa de estado global

Archivo: `state/app_state.py`.

- Define `AppState` como un dataclass con:
  - Usuario.
  - Rol.
  - Ubicación.
  - Empresa y dominio activos.

El controlador la usa como un contenedor simple para compartir contexto entre vistas y servicios sin recurrir a variables globales.

---

## Capa de handlers (orquestación de casos de uso)

Directorio: `handlers/`.

Estructura:

- Submódulos por dominio:
  - `handlers/buscar_key/`
  - `handlers/hsh/`
  - `handlers/jobs/`
  - `handlers/unifilares/`
  - `handlers/pruebas/`
  - `handlers/consultar/`
  - `handlers/actualizar_datos.py`

Responsabilidades típicas de un handler:

- Validar entradas de la UI (empresa, archivos, fechas, parámetros).
- Decidir si es necesario **actualizar datos** antes de un proceso.
- Construir comandos CLI usando `utils.cli.build_cmd`.
- Invocar `TaskRunner.run_subprocess` con:
  - `cmd`: comando completo.
  - `resource_key`: para serializar tareas por recurso (empresa, módulo).
  - `on_progress`: callback que envía líneas a la consola y actualiza la status bar.
  - `on_done`: callback que interpreta el código de retorno, muestra diálogos de éxito/error y reactiva controles.

Son el “pegamento” entre la UI y los scripts CLI, aplicando reglas de negocio y manejo de errores.

---

## Capa de scripts CLI (lógica pesada)

Directorio: `scripts/`.

Características:

- Scripts diseñados para poder ejecutarse:
  - Desde la aplicación (via `main.py --run scripts.<modulo>`).
  - Directamente por consola (modo desarrollo / diagnóstico).
- Principales familias:
  - Importación: `importar_all.py`, `import_scada.py`, `import_hsh.py`, `import_ods.py`.
  - Conversión: `Convertir_all.py`, `Convertir_Unifilares.py`.
  - HSH: `hsh_crear_tag.py`, `hsh_cambiar_key.py`, `hsh_eliminar_tag.py`, `validaciones_hsh.py`.
  - Jobs SCADA: `SCADA_S-A.py`, `eliminar_senales_scada.py`, `cambiar_nombre_senales_scada.py`, etc.
  - Unifilares: `Validacion_unifilares.py`, `Leer_unifilares.py`.
  - PyP: `itcosas_v1_*`, `itcosas_v2_*`, `pyp_checklist.py`, `pyp_soe_monarch.py`, `import_his_soe.py`.
  - Consultas: `consultar_rtu.py`.
  - Utilitarios: `vault_manager.py`, `vault_creator.py`, `test_mongo.py`, `test_pi_query.py`.

Operan sobre archivos (entrada/salida) y sistemas externos, y están diseñados para mantener compatibilidad tanto en desarrollo como en el ejecutable empaquetado.

---

## Capa de utilidades y helpers

Directorio: `utils/` + `util.py`.

Componentes clave:

- `paths.py`: detección de entorno (frozen/dev), raíces de AppData, out/log, helpers para `config/` y `assets/`.
- `cli.py`: construcción de comandos para scripts (modo dev vs ejecutable).
- `task_runner.py`: ejecución asíncrona de subprocesos con integración a Tk.
- `data_checks.py`: verificaciones de disponibilidad de datos locales para distintos modos.
- `last_update.py`: cálculo de “última actualización” de datos por empresa y dataset.
- `ui_actions.py` y `util.py`: helpers de selección de archivos y habilitación de botones.
- `shell.py`: apertura de archivos y carpetas en el sistema operativo.
- `threading_utils.py`: utilidades simples para correr funciones en hilos.

Esta capa reduce duplicaciones y encapsula detalles técnicos recurrentes.

---

## Configuración, plantillas y assets

- `config/`:
  - Perfiles de importación.
  - Mapeos de tablas y bases.
  - Diccionarios de tags.
  - Mapeos de servidores por empresa/dominio.
- `templates/`:
  - Plantillas Excel para inputs (por ejemplo, Jobs, HSH, PyP).
- `assets/`:
  - Iconos, logos y recursos gráficos usados en la UI.

Estos recursos se empaquetan junto al ejecutable y se acceden mediante los helpers de `utils.paths`.

