# 03-01 – Entrypoint y dispatcher

Esta página describe los componentes que se ejecutan primero al iniciar AutoADA y cómo se diferencia el modo GUI del modo “dispatcher de scripts”.

---

## `main.py`: punto de entrada principal

Responsabilidades:

- Actuar como **dispatcher** para scripts CLI cuando se usa la opción `--run`.
- Iniciar la **aplicación GUI** cuando no se especifica `--run`.

Estructura simplificada:

- Función interna `_bundle_root()`:
  - Determina la raíz de recursos para scripts cuando se ejecuta como exe (PyInstaller).
- Función `_cli_dispatcher()`:
  - Si `sys.argv[1] == "--run"`:
    - Interpreta `sys.argv[2]` como nombre de módulo (`scripts.<modulo>`).
    - Ajusta `sys.path` para localizar copias en `_runners/` (en exe) o `scripts/` (en dev).
    - Reescribe `sys.argv` y ejecuta el módulo/archivo con `runpy`.
    - Sale del proceso después de que el script termina.
  - Si no hay `--run`, no hace nada especial y permite que el flujo continúe con la GUI.
- Al final:
  - Importa `AppController` y `LoginWindow`.
  - Define `main()` para iniciar Tk, aplicar el tema y mostrar el login.
  - Llama a `main()` si `__name__ == "__main__"`.

Este diseño permite que el mismo ejecutable sirva tanto como **aplicación de escritorio** como **launcher** de scripts internos.

---

## `login.py`: ventana de acceso al vault

Clase principal: `LoginWindow`.

Responsabilidades:

- Presentar un formulario de login:
  - Usuario.
  - Clave del vault.
  - Botón para mostrar/ocultar la clave.
- Validar inputs:
  - Usuario y clave no vacíos.
- Resolver la ubicación y el vault:
  - Usa `SecurityService.detectar_ubicacion()` para determinar ITCO/REP/Desconocido.
  - Usa `SecurityService.resolve_vault_filename(...)` para sugerir un archivo de vault (`ITCO.bin`, `REPS.bin`, etc.).
  - Usa `vault_manager.resolve_named_vault_path(...)` para localizar físicamente el archivo.
- Intentar cargar el vault:
  - Llama a `load_vault_from_credentials(username, password, vault_path=...)`.
  - Si falla, muestra mensajes de error y permite reintentar.
- Si tiene éxito:
  - Ejecuta el callback `on_success(vault, usuario, rol)`.
  - Cierra la ventana de login.

La ventana también:

- Centra el formulario en pantalla.
- Configura bindings de teclado (`Enter` para aceptar, `Escape` para cancelar).
- Se integra visualmente con el tema `App.*`.

---

## Hook de runtime: `hooks/set_cwd_runtime_hook.py`

Archivo pequeño pero importante:

- Si el código corre en modo ejecutable (`sys.frozen`):
  - Cambia el directorio de trabajo (`cwd`) a la carpeta del ejecutable (`os.path.dirname(sys.executable)`).

Impacto:

- Garantiza que `out/` y `log/` se creen **junto al exe**, no en una carpeta temporal.
- Simplifica la administración de resultados y logs desde el punto de vista del usuario.

Este hook se referencia en los archivos `.spec` de PyInstaller.

---

## Utilidad de CLI: `utils/cli.py`

Función clave: `build_cmd(module: str, *args: str) -> list[str]`.

Responsabilidad:

- Construir el comando correcto para ejecutar scripts CLI, respetando el modo de ejecución:
  - **Modo desarrollo**:
    - Devuelve: `[python, "-u", "-m", module, *args]`.
    - Usa `-u` para salida sin buffering (logs fluidos en la consola embebida).
  - **Modo exe (PyInstaller)**:
    - Devuelve: `[<exe>, "--run", module, *args]`.
    - Confía en que `main.py` actuará como dispatcher.

Todos los handlers utilizan `build_cmd(...)` en lugar de construir comandos manualmente, lo que:

- Asegura consistencia.
- Evita errores por diferencias entre dev y exe.
- Centraliza la lógica de ejecución de scripts en un solo lugar.

---

## Flujo resumido

1. Usuario ejecuta `AutoADA.exe` o `python main.py`.
2. `main.py`:
   - Si recibe `--run`, se comporta como dispatcher de scripts y termina.
   - Si no, levanta la GUI.
3. `main()`:
   - Crea ventana Tk, aplica tema, muestra `LoginWindow`.
4. `LoginWindow`:
   - Valida usuario/clave.
   - Resuelve y desencripta el vault.
   - Llama a `on_success(vault, usuario, rol)`.
5. `on_login_success`:
   - Crea `AppController`.
   - Cierra el login.
6. `AppController`:
   - Configura layout, rutas, estado y entorno.
   - Muestra la vista de bienvenida.

Desde ese momento, la interacción se traslada a los módulos descritos en las siguientes páginas.

