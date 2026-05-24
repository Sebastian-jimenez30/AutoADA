# 02-02 – Flujo de arranque y login

Esta página describe qué ocurre desde que el usuario ejecuta AutomatizADA hasta que se muestra la pantalla de bienvenida, incluyendo el manejo de la CLI y el login con vault.

---

## 1. Dispatcher inicial (`main.py`)

Archivo: `main.py`.

Al iniciar, AutomatizADA verifica si fue invocado en modo “dispatcher de scripts”:

- Si se llama con:  
  `main.py --run scripts.<modulo> [args...]`
  - Se localiza el módulo `scripts.<modulo>`:
    - En modo ejecutable, se buscan copias en `_runners/`.
    - En modo desarrollo, se usa el paquete `scripts/`.
  - Se ajusta `sys.argv` y se ejecuta el módulo o script con `runpy`.
  - Este camino se usa para que el **EXE** pueda actuar como lanzador de scripts internos.

- Si **no** recibe `--run`, continua con el flujo GUI:
  - Importa `AppController`.
  - Importa `LoginWindow`.
  - Llama a `main()` (función principal de la GUI).

Este diseño permite reutilizar el mismo binario tanto para la interfaz como para lanzar scripts en segundo plano.

---

## 2. Creación de la ventana principal y aplicación de tema

En `main()`:

- Se crea un `Tk()` raíz.
- Se establece el título de la ventana.
- Se carga el icono de la aplicación (si está disponible) usando `asset_path("Logodot.ico")`.
- Se aplica el tema gráfico usando `ui/theme.apply_theme(root)`:
  - Estilos `App.*` para frames, labels, botones, comboboxes, etc.

Hasta este punto no se ha creado el `AppController`; primero se requiere el login exitoso.

---

## 3. Ventana de Login y validación de vault

Archivo: `login.py`.

Se crea una instancia de `LoginWindow` que:

- Muestra un formulario con:
  - Usuario.
  - Clave del vault.
  - Botón para mostrar/ocultar la clave.
- Al confirmar:
  - Valida que usuario y clave no estén vacíos.
  - Llama a `SecurityService.detectar_ubicacion()` para determinar ubicación (ITCO/REP/Desconocido).
  - Según la ubicación, resuelve el nombre sugerido de vault (por ejemplo, `ITCO.bin`, `REPS.bin`).
  - Usa `vault_manager.resolve_named_vault_path()` para obtener la ruta del archivo.
  - Llama a `vault_manager.load_vault_from_credentials(usuario, clave, vault_path=...)`.

El proceso de desencriptado:

- Intenta derivar una clave con PBKDF2 usando `usuario + clave`.
- Desencripta el archivo vault (Fernet) y carga un JSON con secretos.
- Si falla, intenta un esquema legacy (solo password).
- Si no puede desencriptar, muestra error “Acceso denegado” y permite reintentar.

Si el vault se carga correctamente:

- El `LoginWindow` llama al callback `on_success(vault, usuario, rol)` suministrado por `main.py`.
- Cierra la ventana de login.

---

## 4. Creación del `AppController`

En el callback `on_login_success` (en `main.py`):

- Se destruye la ventana de login.
- Se instancia `AppController` con:
  - `root` (Tk principal).
  - `base_dir` (directorio base del proyecto/ejecutable).
  - `usuario`, `rol`.
  - `vault` (diccionario de secretos desencriptados).

En `AppController.__init__`:

- Se inicializa `TaskRunner`.
- Se asegura la creación de:
  - `db/` y `tls/` en AppData (`utils.paths.input_root`).
  - `out/` y `log/` junto al ejecutable o proyecto (`utils.paths.output_root`).
- Se determinan:
  - `resource_root` (carpeta de recursos, distinta en dev vs exe).
  - `server_resolver` con acceso a `config/servers.json`.
- Se crea el `AppState` con usuario/rol.
- Se almacena el `vault` y se llama a `secure_env()` para poblar variables de entorno.

Posteriormente se invocan:

- `_setup_window()`: construye layout (sidebar, header, content, statusbar).
- `_setup_menu()`: construye navbar y registra callback de selección.
- `_guard_location()`: verifica que la ubicación detectada sea permitida.
- `_register_frames()`: registra al menos la vista de bienvenida.
- `mostrar_marco(...)`: muestra la vista inicial (bienvenida).

---

## 5. Carga de entorno seguro (`secure_env`)

`AppController.secure_env()` utiliza el contenido del vault para poblar variables de entorno antes de ejecutar scripts:

- Credenciales de Mongo:
  - `MONGO_USER`, `MONGO_PASS`, `MONGO_PORT`, `REPLICA_SET`.
- SSH/túneles:
  - `SSH_USER`, `SSH_KEY_PEM`, `SSH_KEY_PASSPHRASE`, `SSH_PORT`.
- Hosts SCADA/HIS:
  - `SCA_HOSTS`, `HIS_HOSTS`, `HIS_PRIMARY`, `HIS_SECONDARY`.
- TLS para Mongo:
  - `TLS_CERT_KEY_PEM`, `TLS_CA_CERT` (leyendo desde archivos `.pem` si no vienen en el vault).
- ODBC/HIS:
  - `ODBC_DRIVER`, `ODBC_DB`, `ODBC_USER`, `ODBC_PASS`, `ODBC_PORT`.
- PI:
  - `USER_PI`, `PASS_PI`.
- Convenios de runtime:
  - `ADA_BASE_DIR`, `PYTHONUNBUFFERED`, `PYTHONIOENCODING`, `FORCE_COLOR`.

Esto asegura que los scripts CLI puedan acceder a la información necesaria sin leer directamente el vault, y que los logs se decodifiquen correctamente (UTF-8).

---

## 6. Protección por ubicación / hostname

`SecurityService.detectar_ubicacion()`:

- Revisa el hostname de la máquina.
- Lo compara con prefijos autorizados para ITCO/REP.
- Si no concuerda con ninguno, clasifica la ubicación como “Desconocido”.

`AppController._guard_location()`:

- Si la ubicación no es válida para operar, puede:
  - Mostrar un mensaje.
  - Cerrar la aplicación.

Con esto se busca evitar el uso de AutomatizADA en entornos no autorizados.

---

## 7. Transición a la operación normal

Tras el login y la inicialización, el usuario ve:

- La ventana principal con:
  - Navbar lateral.
  - Vista de bienvenida.
  - Barra de estado.

Desde ese momento:

- La navegación por el menú dispara `AppController._on_menu_select`.
- Se construyen vistas específicas usando `FrameRouter`.
- Se gestionan pipelines mediante los handlers y `TaskRunner`.

El flujo de arranque queda completo, y AutomatizADA entra en su ciclo normal de operación.

