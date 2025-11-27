# 02-04 – Gestión de rutas y entornos

AutoADA debe funcionar tanto en **modo desarrollo** como en **modo ejecutable** (PyInstaller), y además separar claramente:

- Dónde se ubican los recursos de solo lectura (config, assets, templates).
- Dónde se escriben los resultados (`out/`) y logs (`log/`).
- Dónde se almacenan dumps y credenciales temporales (AppData).

Esta página resume cómo se manejan rutas y entornos en el código.

---

## Detección de entorno (dev vs ejecutable)

Archivo clave: `utils/paths.py`.

- `is_frozen()`:
  - Devuelve `True` si el código corre dentro de un ejecutable PyInstaller (`sys.frozen`).
- `bundle_root()`:
  - Devuelve la raíz de recursos de solo lectura:
    - En ejecutable: `sys._MEIPASS`.
    - En desarrollo: carpeta del archivo `paths.py`.
- `exec_dir()`:
  - Carpeta donde vive el ejecutable o el script principal.
- `runtime_root()`:
  - Carpeta usada como raíz de trabajo en tiempo de ejecución:
    - En ejecutable: `exec_dir()` (junto al `.exe`).
    - En desarrollo: el directorio de trabajo actual (`os.getcwd()`).

Un hook (`hooks/set_cwd_runtime_hook.py`) se asegura de que, en modo ejecutable, el `cwd` se establezca en la carpeta del `.exe`.

---

## Rutas de AppData y staging

- `appdata_root(app_name="ADA-DOT")`:
  - Usa `%LOCALAPPDATA%` (o `%TEMP%` como fallback).
  - Crea (si no existe) `C:\Users\<usuario>\AppData\Local\ADA-DOT\`.
- `input_root(app_name="ADA-DOT")`:
  - Bajo AppData, asegura las carpetas:
    - `db/` para dumps importados.
    - `tls/` para material TLS/credenciales temporales.

Los scripts de importación y conversión usan estas rutas como **staging** de datos:

- `db/<EMPRESA>/` almacena dumps SCADA/HSH/ODS por empresa.

Esto evita ensuciar la carpeta del ejecutable con archivos grandes o transitorios.

---

## Rutas de salida visibles (`out/` y `log/`)

- `output_root(app_name="ADA-DOT")`:
  - Basado en `runtime_root()`.
  - Crea (si no existen):
    - `out/`
    - `log/`
  - Devuelve la raíz donde se generan los resultados visibles para el usuario.

Helpers adicionales:

- `out_dir_for(empresa)`:
  - Devuelve `out/<EMPRESA>` bajo la raíz de salida y se asegura de que exista.
- `ensure_workdirs()`:
  - Asegura:
    - `input_root()` → `db/` y `tls/` en AppData.
    - `output_root()` → `out/` y `log/` junto al exe/proyecto.
  - Devuelve la raíz de salidas.

`AppController` llama a `ensure_workdirs()` al iniciar, y usa esa raíz como `base_dir` para numerosos procesos.

---

## Recursos de solo lectura (config, assets, templates)

`utils.paths` define:

- `config_path(name)`:
  - Resuelve rutas bajo `config/` de forma robusta (dev vs exe).
- `asset_path(*parts)`:
  - Resuelve rutas bajo `assets/`.

Internamente usan `_resolve_data_path(subdir, *parts)` que:

- En ejecutable:
  - Primero intenta encontrar los recursos junto al exe.
  - Luego en la carpeta de recursos (`bundle_root()`).
- En desarrollo:
  - Usa la raíz del proyecto (`project_root()`), un nivel por encima de `utils/`.

Así, `config/`, `assets/` y `templates/` pueden empaquetarse dentro del exe sin romper el acceso en desarrollo.

---

## Manejo de rutas en scripts CLI

Scripts como `importar_all.py` y `Convertir_all.py` usan `output_root()` y `appdata_root()` para decidir:

- Dónde escribir logs (por ejemplo, `log/importar.log`).
- Dónde crear carpetas de salida:
  - `out/<EMPRESA>/SCADA`
  - `out/<EMPRESA>/HSH`
  - `out/<EMPRESA>/ODSTXT`

Algunos scripts (`Convertir_all.py`) definen helpers internos (`_DB`, `_OUT`) que:

- Combinan `appdata_root` y `output_root` con subcarpetas específicas.

Todo esto mantiene coherencia entre la aplicación y los scripts CLI.

---

## Variables de entorno y contexto de ejecución

`AppController.secure_env()` construye un diccionario de entorno (`env`) para cada subproceso:

- Parte de `os.environ.copy()`.
- Inyecta variables derivadas del vault:
  - Mongo, SSH, ODBC, PI, TLS, hosts, etc.
- Asegura ajustes generales:
  - `ADA_BASE_DIR`: raíz de trabajo (out/log).
  - `PYTHONUNBUFFERED=1`: salida sin buffer para ver logs en tiempo real.
  - `PYTHONIOENCODING=utf-8`: decodificación consistente.
  - `FORCE_COLOR=1`: opcional, para que algunos scripts coloreen output.

Los handlers pasan este `env` a `TaskRunner.run_subprocess` para que los scripts vean un entorno consistente y seguro.

---

## Consulta de estado de datos

Utilidades como `last_update.py` y `data_checks.py` usan las rutas definidas para:

- Buscar la “última actualización” por empresa y dataset (SCADA, HSH, ODSTXT).
- Determinar si existen datos mínimos para ciertos modos (Buscar Keys, Jobs, Unifilares).

Se apoyan en la existencia de:

- Archivos en `out/<EMPRESA>/SCADA|HSH|ODSTXT`.
- Estructura de subcarpetas establecida por los scripts de importación/conversión.

La UI (especialmente la pantalla de bienvenida) usa esta información para informar al usuario del estado de los datos.

