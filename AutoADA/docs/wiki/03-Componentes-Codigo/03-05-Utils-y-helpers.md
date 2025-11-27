# 03-05 – Utils y helpers

La carpeta `utils/` y el módulo `util.py` agrupan funciones y clases de apoyo que se usan en múltiples partes de AutoADA. Esta página resume las más importantes.

---

## `utils/paths.py`

Responsabilidades:

- Detección de entorno:
  - `is_frozen()`, `bundle_root()`, `exec_dir()`, `runtime_root()`.
- Raíces de trabajo:
  - `appdata_root()`: base en `%LOCALAPPDATA%\\ADA-DOT`.
  - `input_root()`: asegura `db/` y `tls/` en AppData.
  - `output_root()`: asegura `out/` y `log/` junto al exe/proyecto.
  - `ensure_workdirs()`: combinación de las anteriores.
- Recursos de solo lectura:
  - `project_root()`: raíz del proyecto en dev.
  - `config_path(name)`: acceso a archivos en `config/`.
  - `asset_path(*parts)`: acceso a archivos en `assets/`.

Uso:

- `AppController` y scripts CLI (importar, convertir, etc.) se apoyan en estas funciones para trabajar sobre rutas coherentes.

---

## `utils/cli.py`

Responsabilidad principal:

- `build_cmd(module, *args)`:
  - Devuelve:
    - `[python, "-u", "-m", module, *args]` en dev.
    - `[<exe>, "--run", module, *args]` en exe.

Uso:

- Handlers en `handlers/` construyen comandos para scripts CLI usando esta función exclusivamente.

---

## `utils/task_runner.py`

Resume la **ejecución asíncrona de subprocesos**:

- Usa `subprocess.Popen` para lanzar comandos.
- Captura stdout + stderr unificados.
- Encola líneas en un `queue.Queue`.
- Usa `tk_root.after` para:
  - Bombear líneas hacia callbacks (`on_progress`).
  - Notificar finalización (`on_done`).
- Mantiene locks por `resource_key` para serializar tareas por recurso.
- Exponen:
  - `run_subprocess(cmd, resource_key, env, cwd, on_progress, on_done)`.
  - `add_state_listener(listener)`.
  - `is_running()`, `stop_all()` y lógica de “force kill”.

Uso:

- `AppController` mantiene una instancia de `TaskRunner`.
- Handlers lo utilizan para correr scripts pesados sin bloquear la UI.

---

## `utils/data_checks.py`

Funciones para verificar disponibilidad de datos locales:

- `_dir_has_exts(path, exts, recursive)`: helper interno.
- `find_mode_data_ready(base_dir, empresa)`:
  - Comprueba que existan:
    - `SCADA`: CSV en `out/<EMPRESA>/SCADA`.
    - `HSH`: `groups.csv` y `lookup_table.csv` en `out/<EMPRESA>/HSH`.
    - `ODSTXT`: TXT/CSV en `out/<EMPRESA>/ODSTXT`.
- `jobs_mode_data_ready(base_dir, empresa)`:
  - Verifica que existan CSV SCADA mínimos para Jobs.
- `unifilares_mode_data_ready(base_dir, empresa)`:
  - Verifica que existan ODS/ODSTXT necesarios para unifilares.

Uso:

- Handlers de Buscar Keys, Jobs y Unifilares usan estas funciones para decidir si se habilitan ciertos botones o se fuerza una actualización de datos.

---

## `utils/last_update.py`

Funciones para calcular la “última actualización” de datos:

- `_max_mtime_in(path)`: mtime más reciente en un directorio (recursivo).
- `_out_candidates(base_dir, empresa)`: posibles raíces de `out/` para dev y exe.
- `last_update_for(base_dir, empresa, subfolders)`:
  - Devuelve `(nombre_subcarpeta, epoch_mtime)` de la carpeta más reciente entre las dadas.
- `last_update_text(...)`:
  - Devuelve un string listo para UI: fecha/hora + “hace X tiempo”.

Uso:

- La vista de bienvenida muestra estado de SCADA/HSH/ODSTXT utilizando estas funciones.

---

## `utils/ui_actions.py` y `util.py`

### `utils/ui_actions.py`

- Maneja selección de archivos desde la UI:
  - `seleccionar_archivo(...)`: selector de archivos con lógica específica para unifilares y distintos tipos de inputs.
  - `mostrar_boton_seleccionar_archivo_unifilares(app)`: crea y configura botones de selección/ejecución para unifilares, incluyendo bindings a variables `StringVar`/`BooleanVar`.
  - `seleccionar_archivo_simple(...)`: API genérica para seleccionar uno o varios archivos.

### `util.py`

- Compatibilidad y helpers legacy:
  - `verificar_habilitar_boton(...)`: lógica para habilitar/deshabilitar botones según empresa, dominio, checkbox y selección de archivo.
  - `ejecutar_script(...)`: ejecución síncrona simple de scripts (menos usada en favor de `TaskRunner`).
  - `limpiar_marco(marco)`: destruye widgets hijos de un frame.

Uso:

- `AppController.seleccionar_archivo` delega en `ui_actions` o en la versión legacy según parámetros.
- Algunas vistas y handlers utilizan `verificar_habilitar_boton` para controlar habilitación de acciones.

---

## `utils/shell.py`

Funciones para interactuar con el sistema operativo:

- `open_path(path)`: abre un archivo/carpeta con la app predeterminada (usa `os.startfile`, `open`, `xdg-open` según plataforma).
- `open_in_file_manager(path, select)`: abre el explorador de archivos mostrando la carpeta o seleccionando el archivo.
- `reveal_path(path)`: atajo para “revelar” un archivo en el explorador.

Uso:

- `success_dialog` las usa para implementar los botones de:
  - “Abrir archivo”.
  - “Mostrar carpeta”.
  - “Copiar ruta”.

---

## `utils/threading_utils.py`

Helper simple:

- `run_in_thread(fn, on_finally=None, *args, **kwargs)`:
  - Ejecuta `fn` en un hilo daemon.
  - Llama a `on_finally` al terminar (en el mismo hilo).

Uso:

- Puede emplearse en casos donde un trabajo ligero pero bloqueante no amerita un subproceso completo.

---

## Resumen

Los módulos de `utils/`:

- Encapsulan detalles de entorno, rutas, CLI, ejecución asíncrona y UI repetitiva.
- Permiten que controladores, vistas y handlers mantengan su lógica **enfocada en el dominio**, sin reimplementar utilidades técnicas.

Antes de escribir “helpers” nuevos, conviene revisar `utils/` para reutilizar o extender lo ya existente.

