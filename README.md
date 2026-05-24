# Automatismo ADA - Documentacion General

## 1. Proposito y alcance
Automatismo ADA (AutoADA) es una aplicacion de escritorio desarrollada en Python/Tkinter para apoyar los flujos operativos del equipo DOT Intercolombia. El sistema centraliza procesos que tradicionalmente se ejecutaban manualmente con scripts ad-hoc: importacion y conversion de datos SCADA/HSH/ODS, generacion y mantenimiento de senales, validacion de unifilares, ejecucion de pruebas PyP y consultas a RTU/SAS. La aplicacion proporciona una interfaz grafica unificada que abstrae los detalles de linea de comandos y las ubicaciones de archivos de trabajo.

El proyecto integra multiples scripts especializados, configuraciones y plantillas de soporte. AutoADA coordina la preparacion de datos (descargas remotas, conversiones y verificaciones), ejecuta los scripts con los parametros correctos y entrega los resultados finales listos para uso operativo en carpetas `out/` y `log/` proximas al ejecutable. Todo el flujo se acompana con mensajes de estado y una consola embebida que exponen el avance en tiempo real.

Este documento describe en detalle la arquitectura, el flujo general de funcionamiento, la organizacion del codigo, las tecnologias empleadas y las particularidades de cada funcionalidad disponible en la aplicacion.

## 2. Resumen ejecutivo
- Aplicacion desktop Tkinter (`main.py`, `controllers/app_controller.py`) que levanta vistas dinamicas alojadas en `interfaces/`.
- Capas bien definidas: vistas -> controlador -> handlers -> scripts CLI, con servicios de soporte (`services/`) y utilidades (`utils/`).
- Ejecucion asyncrona de pipelines mediante `utils/task_runner.TaskRunner`, evitando bloquear la UI mientras corren scripts intensivos.
- Persistencia de datos de trabajo en estructuras `out/<empresa>/...` y `log/` junto al binario (o al CWD en desarrollo), ademas de staging en `%LOCALAPPDATA%\ADA-DOT`.
- Seguridad integrada: autenticacion via vault cifrado (`scripts/vault_manager.py`), restriccion por hostname (`services/security_service.py`) y resolucion controlada de servidores (`services/server_resolver.py`).
- Empaquetado con PyInstaller (`AutoADA.spec`) incluyendo assets, configuraciones, plantillas y runners de scripts para distribucion como ejecutable unico.

## 3. Arquitectura global

### 3.1 Capas principales
1. **Interfaz de usuario (Tkinter/ttk)**: componentes reutilizables (`ui/`) y vistas especificas (`interfaces/*.py`) que definen formularios, consolas y acciones.
2. **Controlador de aplicacion** (`controllers/app_controller.py`): orquesta navegacion, estado, validaciones preliminares, status bar y despacho de tareas.
3. **Ruteo de vistas** (`controllers/frame_router.py`): registra fabricas de frames para cada opcion del menu lateral y construye vistas bajo demanda.
4. **Servicios** (`services/`): logica transversal para seguridad de entorno (`security_service`) y resolucion de servidores/dominios (`server_resolver`).
5. **Handlers** (`handlers/*.py`): capa de orquestacion que valida entradas, arma comandos, invoca `TaskRunner`, captura logs y entrega resultados al usuario.
6. **Scripts CLI** (`scripts/*.py`): implementaciones pesadas (importar/convertir, buscar keys, validar HSH, generar reportes PyP, etc.) pensadas para ejecutarse tanto en desarrollo como dentro del EXE mediante el dispatcher `main.py --run`.
7. **Configuracion y datos auxiliares** (`config/`, `templates/`, `assets/`, `scripts/cifrar/`, `scripts/sh/`): JSON con perfiles y diccionarios, plantillas Excel, iconografia y certificados TLS para conexiones remotas.

### 3.2 Relaciones clave
```
Usuario
  |
  v
Tkinter Views (interfaces/)
  |
  v
AppController (controllers/app_controller.py)
  |
  v
Handlers dedicados (handlers/*.py)
  |
  v
TaskRunner -> build_cmd -> scripts/*.py -> archivos en out/ y log/
                     ^
                     |
             Servicios (security_service, server_resolver)
                     ^
                     |
            Configuracion JSON y vault cifrado
```

El controlador central mantiene el estado (`state/app_state.py`), administra la barra de estado (`ui/components/statusbar.py`), actualiza la consola (`ui/components/console.py`) y asegura que los handlers dispongan de un entorno controlado (variables de entorno, rutas temporales y permisos). Los scripts CLI, a su vez, utilizan `utils/paths` y `config/import_profiles.json` para localizar origenes remotos y carpetas locales.

## 4. Flujo de arranque y ciclo principal
1. **Dispatcher inicial** (`main.py`): permite invocar scripts con `python main.py --run module args` (clave para el ejecutable PyInstaller). Si no hay bandera `--run`, continua con el flujo GUI.
2. **Login seguro** (`login.py`): solicita usuario y clave para derivar la llave Fernet y desencriptar `vault.bin` via `scripts/vault_manager.load_vault_from_credentials`. El vault contiene secretos para conexiones remotas (SSH, Mongo, ODBC, etc.).
3. **Inicializacion de Tk**: se aplica el tema personalizado (`ui/theme.py`), se fija titulo e icono (`assets/logodot.ico`) y se centra la ventana.
4. **Creacion de AppController**: recibe el vault y los metadatos de usuario/rol. Llama a `utils.paths.ensure_workdirs()` para garantizar la existencia de `%LOCALAPPDATA%\ADA-DOT\{db,tls}` y de `out/` + `log/` junto al ejecutable.
5. **Controles de seguridad**: `SecurityService.detectar_ubicacion()` valida el hostname contra una lista permitida. Si la ubicacion es desconocida, se cierra la aplicacion.
6. **Resolucion de configuraciones**: `ServerResolver` carga `config/servers.json` y expone mapas inmutables para empresas y dominios (utilizados por los combobox de cada vista).
7. **Registro de vistas**: se registra la vista de bienvenida y, al navegar, se registran dinamicamente los demas marcos (`FrameRouter.register`).
8. **UI reactiva**: cada vista inicializa controles, vincula variables `tk.StringVar/BooleanVar`, conecta botones a handlers y crea una `LogConsole` y la barra de estado compartida.
9. **Ejecucion de pipelines**: al lanzar una accion, el handler prepara el entorno (`AppController.secure_env()`), arma comandos con `utils.cli.build_cmd`, usa `TaskRunner.run_subprocess` para correr los scripts en segundo plano y va actualizando la consola/StatusBar. Al terminar, muestra `ui/components/success_dialog.show_success_with_open` con accesos rapidos a los archivos generados.
## 5. Seguridad y manejo de credenciales
- **Restriccion por hostname**: `services/security_service.SecurityService.detectar_ubicacion()` identifica la ubicacion (ITCO, REP o Desconocido) con base en prefijos de hostname. Solo equipos catalogados como ITCO o REP pueden operar la aplicacion; de lo contrario, el controlador cierra la ventana principal.
- **Vault cifrado**: el login usa `scripts/vault_manager.load_vault_from_credentials()` para derivar una clave PBKDF2 (username + password) y desencriptar `scripts/vault.bin` (formato Fernet). Se mantiene compatibilidad legacy con contrasenas antiguas.
- **Inyeccion controlada de secretos**: `AppController.secure_env()` propaga valores del vault (Mongo user/pass, hosts, llaves SSH, certificados TLS) a variables de entorno antes de lanzar cada subproceso. Ningun script lee directamente el vault; reciben solo lo necesario via entorno.
- **Separacion de rutas sensibles**: `utils.paths.appdata_root()` utiliza `%LOCALAPPDATA%` para staging de credenciales y dumps (`db/`, `tls/`), mientras que `utils.paths.output_root()` mantiene resultados (`out/`, `log/`) al lado del ejecutable, evitando exponer archivos transitorios en la carpeta instalacion.
- **Material TLS/SSH**: certificados y llaves se distribuyen en `scripts/cifrar/` y se referencian via vault/environment. Para conexiones remotas se emplean bibliotecas como `paramiko`, `sshtunnel` y `pymongo` (marcadas como hiddenimports en `AutoADA.spec`).
- **Confirmaciones de acciones criticas**: operaciones HSH que modifican datos (`handlers.hsh.ejecutar_crear_tag_hsh`) solicitan confirmacion explicita antes de insertar cambios.

## 6. Servicios y utilidades clave
- **Estado global** (`state/app_state.py`): almacena usuario, rol, ubicacion fisica y contextos seleccionados (empresa/dominio) para compartirlos entre vistas.
- **Resolucion de servidores** (`services/server_resolver.ServerResolver`): mapea claves de empresa y dominio a hostnames leidos de `config/servers.json`, exponiendo informacion inmutable para la UI y generando strings de conexion para los scripts.
- **Ejecucion asincronica** (`utils/task_runner.TaskRunner`): levanta subprocesos con stdout capturado linea a linea, serializa ejecuciones por recurso (`resource_key`), escribe logs opcionalmente y garantiza reintentos seguros en la UI mediante `root.after`.
- **Builder de comandos** (`utils/cli.build_cmd`): abstrae la diferencia entre modo desarrollo (invoca `python -u -m module`) y modo empaquetado (invoca `AutoADA.exe --run module`). Todas las invocaciones de scripts pasan por este helper.
- **Gestion de rutas** (`utils/paths`): detecta cuando la app esta congelada, resuelve carpetas de entrada/salida, expone `ensure_workdirs()` y helpers para ubicar configuraciones o assets sin importar el contexto (dev vs PyInstaller).
- **Verificacion de datos locales** (`utils/data_checks`): funciones `find_mode_data_ready`, `jobs_mode_data_ready` y `unifilares_mode_data_ready` validan la existencia de CSV/TXT requeridos antes de ejecutar pipelines. Si faltan, la UI fuerza la opcion "Actualizar BD".
- **Ultimas actualizaciones** (`utils/last_update`): inspecciona mtimes de subcarpetas `out/<empresa>/<SCADA|HSH|ODSTXT>` tanto en la ruta local como junto al ejecutable para mostrar mensajes del tipo "Ultima actualizacion: YYYY-MM-DD HH:MM (hace X)".
- **Helpers UI** (`util.py` y `utils/ui_actions.py`): controlan habilitacion de botones al seleccionar empresa/dominio/archivo, administran dialogos de seleccion de archivos (incluyendo multiples TXT para unifilares) y limpian marcos anteriores al cambiar de vista.
- **Componentes reutilizables** (`ui/components/`):
  - `navbar.py` construye el menu lateral con secciones plegables y logo DOT.
  - `console.LogConsole` pinta la consola con tags `info/warn/error` y autoscroll.
  - `statusbar.StatusBar` muestra mensajes, barra de progreso deterministica o indeterminada y estilos consistentes.
  - `success_dialog.show_success_with_open` entrega accesos directos para abrir, revelar o copiar rutas de archivos generados.
## 7. Interfaz de usuario y navegacion
- **Tema visual** (`ui/theme.py`): define paleta corporativa (PRIMARY, ACCENT, BACKGROUND), tipografias y estilos `App.*`. Ajusta `ttk.Style` al tema `clam`, personaliza botones laterales y campos de formulario.
- **Layout principal**: `AppController` crea dos columnas: barra lateral (navbar) y contenedor central (`self.content`). Cada vista (`BaseView.center_box`) centra un panel con padding generico, garantizando consistencia entre modulos.
- **Navbar con scroll** (`ui/components/navbar.py`): agrupa opciones en secciones plegables: `Buscar`, `HSH`, `Jobs`, `Unifilares`, `Pruebas PyP`, `Consultar`, ademas del boton "Inicio". Mantiene estado activo para resaltar la opcion seleccionada.
- **Status bar**: cada handler usa `start_status`, `set_status`, `success_status`, `error_status` (wrappers en `AppController`) para notificar progreso y resultados.
- **Consola embebida**: todas las vistas operativas disponen de una `LogConsole` que acumula stdout de scripts con colores segun criticidad.
- **Dialogos de confirmacion y exito**: se reemplazaron `messagebox` simples por el dialogo personalizado `success_dialog` que permite abrir o revelar el archivo generado y copiar su ruta.
- **Variables de control**: combos y checkboxes se enlazan a `StringVar`/`BooleanVar` y usan trazas (`trace_add`) para habilitar/deshabilitar acciones en tiempo real.
## 8. Flujo de datos y directorios
- **AppData (`%LOCALAPPDATA%\ADA-DOT`)**: staging seguro para descargas (`db/<empresa>/SCADA|HSH|ODS`) y artefactos temporales (`tls/`). Gestionado automaticamente por `utils.paths.input_root`.
- **Raiz de ejecucion** (`utils.paths.output_root`): ubicacion junto al EXE (o CWD) donde se generan carpetas `out/` y `log/`. Todos los reports y planillas finales se escriben aqui.
- **Estructura `out/` tipica**:
  - `out/<EMPRESA>/SCADA|HSH|ODSTXT` con CSV convertidos.
  - `out/Find_key/Find_Key.xlsx` resultado de busquedas de keys.
  - `out/Load/` y `out/Delete/` con salidas de procesos Jobs.
  - `out/Validaciones_<EMPRESA>/` para validaciones HSH.
  - `out/pruebas/` para pipelines PyP.
- **`log/`**: contiene `importar.log`, `buscar_keys.log`, `Scada_load.log`, etc. Los scripts agregan en append para mantener historial por sesion.
- **Plantillas y assets**: `templates/` almacena formatos Excel base (por ejemplo `Checklist_V1.xlsx`, `ProyectoPI_EstandarSenales&TAG.xlsx`). `assets/` contiene iconos y logos utilizados por la UI.
- **Soporte CLI**: scripts auxiliares (`scripts/sh/*.sh`) y certificados (`scripts/cifrar/*.pem`) se empaquetan pero no se modifican en ejecucion.
## 9. Pipelines funcionales

### 9.1 Buscar Key / Buscar Keys
- **Vistas**: `interfaces/marco_buscar_key.py` ofrece dos modos: buscar una cadena manual (opcion 1) o procesar un Excel con multiples claves (opcion 2).
- **Validaciones previas**: `handlers.buscar_key.common._validar_keys` exige que cada key sea de 8 digitos o contenga comodines `%`. `utils/data_checks.find_mode_data_ready` revisa si existen CSV locales de SCADA, HSH y ODSTXT; si faltan, la UI bloquea el checkbox "Actualizar BD" en `True`.
- **Actualizacion de datasets** (cuando procede):
  1. `scripts.importar_all servidor empresa sca,hsh,ods --usecase buscar_keys` descarga dumps remotos via SSH/ODBC.
  2. `scripts.Convertir_all empresa Buscar_keys --only sca,hsh,ods,ods_csv` transforma los dumps en CSV listos para consulta.
- **Busqueda**:
  - Modo manual: `scripts.buscar_key` recibe la cadena, crea `out/Find_key/Find_Key.xlsx` y resalta coincidencias junto con DB/Tabla/Campo/Record (`config/buscar_key.json` + `config/db_names.json` definen mapeos y etiquetas).
  - Modo archivo: `scripts.buscar_keys` procesa la columna A del Excel seleccionado, replica la logica de filtrado y genera el mismo reporte consolidado.
- **Resultados**: al finalizar, el handler habilita el boton y abre un dialogo de exito apuntando a `out/Find_key/Find_Key.xlsx`. La consola detalla cada archivo analizado.

### 9.2 HSH (validacion y creacion de tags)
- **Vistas**: `interfaces/marco_hsh.py` expone "Crear Tag HSH" y "Validar". Muestra ultimas actualizaciones de SCADA/HSH y administra checkboxes de sincronizacion.
- **Validacion** (`handlers.hsh.ejecutar_validacion_hsh`):
  1. Importa SCADA+HSH principal (y respaldo si aplica) con `--usecase hsh_validar --flex`.
  2. Convierte granularmente SCADA y HSH para cada empresa (`scripts.Convertir_all ... --only sca` y `--only hsh`).
  3. Ejecuta `scripts.validaciones_hsh`, que produce reportes en `out/Validaciones_<EMPRESA>/` (varios XLSX).
  4. El dialogo de exito lista todos los archivos de validacion encontrados.
- **Creacion/validacion de tags** (`ejecutar_crear_tag_hsh`):
  1. Valida que exista un Excel con columnas requeridas y resuelve el servidor (dominio CC).
  2. Si se marca "Actualizar BD", repite import + conversion con `--usecase hsh_crear_tag` y aplica conversiones granulares para empresa principal y respaldo.
  3. Ejecuta `scripts.hsh_crear_tag` con `--input <excel>` y, si el usuario confirmo, `--apply --server <hostname>` para insertar en HSH. El script emite rutas `REPORT_PATH`, `INFO_PATH`, `QUERY_PATH` en stdout; el handler las captura y las muestra en el dialogo de exito.
  4. Se actualiza la etiqueta de ultima carga (combinando SCADA y HSH) y se restablecen los botones de validar/crear.
- **Controles adicionales**: cuando los datos locales estan incompletos se fuerza `Actualizar BD`. Se soporta empresa "respaldo" (ITCO<->TRA, REPS<->REPP) para generar reportes cruzados.

### 9.3 Jobs (crear, eliminar, cambiar nombre de senales)
- **Vistas**: `interfaces/marco_jobs.py` define tres flujos con UI similar (seleccion de empresa, checkbox de actualizacion, seleccion de archivo Excel y consola compartida).
- **Crear Senales** (`handlers.jobs.ejecutar_crear_senales`):
  1. Si corresponde, ejecuta `scripts.importar_all servidor empresa sca --usecase jobs_crear_senales`.
  2. Convierte datasets relevantes con `scripts.Convertir_all empresa jobs`.
  3. Valida entrada mediante `scripts.scan_data` (si retorna 2 -> errores, se abre detalle leyendo `out/validacion_errores.txt`).
  4. Ejecuta `scripts.SCADA_S-A` para generar cargas y llaves.
  5. Entrega `out/Load/10_SCADA.csv`, `out/Load/32_FEP.csv`, `out/Load/Senales_with_keys.xlsx`.
- **Eliminar Senales** (`ejecutar_eliminar_senales`): pipeline equivalente pero llama `scripts.eliminar_senales_scada`. Resultados principales: `out/Delete/Delete_scada.csv`, `out/Delete/change_key.csv`, `out/Delete/Delete_controls.csv`.
- **Cambiar nombre** (`ejecutar_cambiar_nombre_senales`): reusa import/convert si se solicita actualizacion y finalmente invoca `scripts.cambiar_nombre_senales_scada`, generando `out/Name/change_key.csv`.
- **Mensajeria**: cada etapa loguea comandos `[IMPORT]`, `[CONVERT]`, `[SCAN]`, `[SCADA S-A]`, `[ELIMINAR]`, `[CAMBIO]` en la consola, y la barra de estado detalla acciones actuales.

### 9.4 Unifilares
- **Vista**: `interfaces/marco_unifilares.py` combina selecion de empresa/dominio, checkbox "Actualizar BD", botones "Importar", "Seleccionar archivo" y "Ejecutar", mas consola.
- **Importacion/Conversion** (`handlers.unifilares.importar_y_convertir_unifilares`):
  1. Importa SCADA (`--usecase validar_unifilares`) y ODS mediante `scripts.importar_all` (lanza dos comandos paralelos para SCADA y ODS).
  2. Tras la descarga, ejecuta `scripts.Convertir_all empresa unifilares --only ods,ods_csv` para normalizar archivos.
  3. Opcionalmente soporta conversion en paralelo y espera a que ODS termine para disparar conversion.
- **Validaciones** (`handlers.unifilares.ejecutar_validaciones_unifilares`):
  1. Requiere archivos TXT seleccionados (multiseleccion). Estos se pasan a `scripts.Validacion_unifilares` junto con la empresa.
  2. Captura stdout para detectar rutas de reportes y actualizar la barra de estado.
  3. Presenta dialogo con archivos generados dentro de `out/Validacion_Unifilares/`.
- **Sincronizacion UI**: cuando "Actualizar BD" esta activo, los botones de archivo/ejecutar se deshabilitan hasta que finaliza la importacion. Las etiquetas de ultima actualizacion se refrescan con `utils.last_update`.

### 9.5 Pruebas PyP
- **Vista**: `interfaces/marco_pruebas_pyp.py` ofrece dos tabs logicos (version 1 y version 2). Incluye seleccion de empresa, fecha, ventanas de tiempo (`pyp_fecha`, `pyp_hora_inicio/fin`), selecciones de archivos (Checklist, EventosDiario, VAREXP, TMWGateway o equivalentes v2) y una lista de estaciones derivada automaticamente del archivo de checklist.
- **Pipeline v1** (`handlers.pruebas.ejecutar_pruebas_itcosas_v1_pipeline`):
  A) `scripts.itcosas_v1_ioa` (usa archivos tmwgateway y varexp) genera `Direcciones.csv`.
  B) `scripts.itcosas_v1_soe_local` combina `Direcciones.csv` y eventos diarios para producir `SOE_Local.csv`.
  C) `scripts.import_his_soe` (opcional por estacion) consulta HIS y consolida en `out/pruebas/data.csv`.
  D) `scripts.pyp_soe_monarch` integra datos de SCADA, checklist y `data.csv` para generar SOE Monarch.
  E) `scripts.pyp_checklist` arma el checklist final (XLSX).
  Pasos A y C corren en paralelo; los restantes esperan dependencias. El handler monitoriza progresos con prefijos `[IOA]`, `[SOE LOCAL]`, `[HIS]`, `[SOE MONARCH]`, `[CHECKLIST]`.
- **Pipeline v2** (`ejecutar_pruebas_itcosas_v2_pipeline`): reemplaza scripts por `scripts.itcosas_v2_*` y ajusta insumos (por ejemplo `itcosas_v2_checklist`). Mantiene la orquestacion y genera reportes actualizados en `out/pruebas/`.
- **Salidas**: ademas de los CSV/XLSX intermedios, los scripts emiten mensajes `REPORT_PATH` que el handler agrega a la lista para el dialogo de exito.

### 9.6 Consultar RTU/SAS
- **Vista**: `interfaces/marco_consultar.py` carga `out/<empresa>/SCADA/32_6.csv` para poblar una lista de RTU/SAS (Record:Name). Permite filtrar por texto y seleccionar multiples registros.
- **Ejecucion** (`handlers.consultar.ejecutar_consulta_rtu`): construye `scripts.consultar_rtu --empresa <EMP> --rtus "rtu1, rtu2"`, muestra avances "Consultando..." en la barra y captura rutas `RTU_REPORT:` del stdout.
- **Resultados**: al finalizar, abre `show_success_with_open` con el reporte indicado (normalmente un XLSX dentro de `out/Consultar/` o similar). Si no se reporta ruta, instruye revisar la consola.

### 9.7 Vista de bienvenida
- `interfaces/marco_bienvenida.py` resume el estado de los datasets SCADA/HSH/ODSTXT por empresa (usando `utils.last_update`). Desde aqui se puede abrir directamente la vista de actualizacion de keys o refrescar estadisticas.
## 10. Scripts tecnicos destacados (`scripts/`)
- **importar_all.py**: orquestador de descargas SCADA/HSH/ODS parametrizado por `config/import_profiles.json`. Ejecuta scripts remotos (via SSH) y copia dumps hacia `AppData/db/...`.
- **Convertir_all.py**: convierte dumps a CSV/Excel finales. Admite modos `Buscar_keys`, `Validar_HSH`, `jobs`, `unifilares` y bandera `--only` (sca, hsh, ods, ods_csv). Utiliza `pandas`, `numpy`, `openpyxl` y `concurrent.futures` para procesar en paralelo.
- **buscar_key.py / buscar_keys.py**: buscan coincidencias de keys en SCADA/HSH/ODSTXT, usando configuraciones especficas de columnas y nombres amigables (`config/buscar_key.json`, `config/db_names.json`).
- **hsh_crear_tag.py**: valida y opcionalmente inserta tags en HSH; genera reportes de validacion y consulta, compatibles con las rutas capturadas por el handler.
- **validaciones_hsh.py**: aplica reglas de consistencia sobre CSV de SCADA/HSH y produce planillas de hallazgos.
- **scan_data.py, SCADA_S-A.py, eliminar_senales_scada.py, cambiar_nombre_senales_scada.py**: conjunto de scripts para preparar, validar, generar o limpiar senales SCADA segun casos de uso de Jobs.
- **Validacion_unifilares.py** y **Convertir_Unifilares.py**: manejan conversion ODSTXT y validaciones especificas para archivos unifilares.
- **Pruebas PyP**: `itcosas_v1_ioa.py`, `itcosas_v1_soe_local.py`, `pyp_soe_monarch.py`, `pyp_checklist.py`, `import_his_soe.py` y sus pares v2 coordinan la generacion de reportes de pruebas.
- **consultar_rtu.py**: realiza consultas sobre RTU/SAS, emitiendo reportes y mensajes `RTU_REPORT`.
- **Utilities adicionales**: `vault_manager.py` (manejo de vault), `vault_creator.py` (creacion de nuevos vault), `test_mongo.py` (diagnostico de conexion), `import_resolvers.py` y `functions.py` (helpers compartidos entre scripts).
## 11. Configuracion y datos auxiliares (`config/`)
- **servers.json**: mapea ids de empresa (`1-4`) y dominios (`1=QA`, `2=CC`) a hostnames (`itco1qds01`, `itco1sca01`, etc.). `ServerResolver` se apoya en este archivo.
- **import_profiles.json**: define los perfiles por defecto y por caso de uso para `importar_all`. Incluye comandos remotos (`remote_cmd`), ubicaciones `from_path`, filtros Mongo y banderas `flex`.
- **buscar_key.json**: describe, por archivo CSV, las columnas que deben consultarse durante la busqueda de keys.
- **db_names.json**: provee etiquetas amigables para tablas (p. ej. `32_6` -> `FEP RTU_DATA`).
- **diccionario_tags.json**: diccionario extenso con metadatos de tags usado por scripts HSH.
- **scada.json**: catalogo de configuraciones SCADA utilizadas por scripts de Jobs y validaciones.
- Los archivos se empaquetan dentro del ejecutable (ver `AutoADA.spec`) y `utils.paths.config_path` garantiza su acceso tanto en dev como en produccion.
## 12. Construccion y despliegue
- **PyInstaller** (`AutoADA.spec`): empaqueta `main.py` como EXE con icono `assets/Logodot.ico`. Incluye carpetas completas (`assets`, `config`, `db`, `scripts` como `_runners`, `templates`, `scripts/vault.bin`).
- **Hidden imports**: se agregan dependencias dinamicas (cryptography, pymongo, sshtunnel, paramiko, tkcalendar, pyxlsb, pandas, numpy, openpyxl, pyodbc) para evitar errores de importacion en runtime.
- **Binaries**: `collect_dynamic_libs('pyodbc')` asegura que las DLL necesarias para ODBC acompanen al EXE.
- **Runtime hook** (`hooks/set_cwd_runtime_hook.py`): fuerza `os.chdir` a la carpeta del ejecutable cuando corre congelado, de modo que las rutas relativas a `out/` y `log/` funcionen de igual forma que en desarrollo.
- **Dispatcher**: todos los scripts CLI se ejecutan via `main.py --run module`, lo cual habilita reutilizar el mismo EXE como lanzador y simplifica updates.
## 13. Dependencias externas principales
- **Tkinter / ttk**: base de la interfaz de escritorio.
- **Pillow (PIL)**: carga y escala iconos (`ui/theme.py`, navbar).
- **pandas, numpy, openpyxl, tkcalendar, pyxlsb**: manipulacion de datos tabulares y lectura/escritura de Excel/CSV.
- **cryptography**: cifrado/dcifrado del vault (Fernet + PBKDF2).
- **paramiko, sshtunnel, pymongo, pyodbc**: conectividad remota (SSH, tuneles, MongoDB, ODBC para HIS/SCADA).
- **concurrent.futures, threading, subprocess**: utilizados ampliamente en scripts y en `TaskRunner` para ejecucion paralela y captura de logs.
## 14. Registro y monitoreo
- **Logs locales**: cada script escribe en `log/*.log` (p. ej. `importar.log`, `buscar_keys.log`, `Scada_load.log`). Los handlers limpian la consola al iniciar y reenvian cada linea (filtrando `ERROR/WARNING` para notificar en la barra de estado).
- **Dialogos enriquecidos**: `success_dialog` ofrece botones para abrir, mostrar en carpeta y copiar rutas, ademas de ejecutar la accion solicitada y autocerrar.
- **Manejo de errores**: si un subproceso retorna codigo distinto de cero, los handlers reactivan los botones, muestran `messagebox.showerror` y conservan la salida en consola para diagnostico. Casos especiales (validacion fallida en `scan_data`) abren un resumen de errores.
- **Actualizacion visual**: `StatusBar` cambia de estilo segun el estado (`start`, `success`, `error`) y controla barra de progreso determinate cuando se conoce el avance.
## 15. Estructura del repositorio
- `main.py` / `login.py`: punto de entrada de la aplicacion y ventana de autenticacion.
- `controllers/`: `app_controller.py` (core de la aplicacion) y `frame_router.py`.
- `interfaces/`: vistas Tkinter por funcionalidad (bienvenida, buscar_key, jobs, hsh, unifilares, pruebas_pyp, consultar).
- `handlers/`: capas de negocio para cada vista (buscar_key/ (cadena, archivo), hsh/ (validar, crear, eliminar), jobs/ (crear, eliminar, cambiar_nombre), pruebas/ (itcosas_v1, itcosas_v2), unifilares/ (importar, validar), consultar/ (rtu)).
- `services/`: servicios transversales (`security_service`, `server_resolver`).
- `state/`: dataclasses de estado global.
- `ui/`: tema, componentes reutilizables (navbar, console, statusbar, dialogs) y helpers de vista.
- `utils/`: herramientas compartidas (paths, cli, task_runner, last_update, data_checks, ui_actions, shell helpers).
- `scripts/`: scripts CLI principales, runners auxiliares, certificados (`cifrar/`) y shells (`sh/`).
- `config/`: archivos JSON de configuracion y diccionarios.
- `assets/`: iconos/logos de la aplicacion.
- `templates/`: plantillas Excel de referencia.
- `out/` y `log/`: carpetas generadas durante la ejecucion con resultados y bitacoras.
- `hooks/`: runtime hook utilizado por PyInstaller.
- `AutoADA.spec`: especificacion de build.
## 16. Buenas practicas operativas y notas
- Verificar la seccion de bienvenida para confirmar la antiguedad de datos antes de lanzar procesos pesados. Si los datasets estan desactualizados, marcar "Actualizar BD" para forzar importaciones frescas.
- Supervisar la consola durante la ejecucion; los handlers reescriben prefijos (`[IMPORT]`, `[CONVERT]`, `[SCAN]`, etc.) que ayudan a identificar rapidamente el paso donde ocurri� un error.
- Conservar el vault actualizado y restringir su distribucion. Cualquier cambio en credenciales requiere regenerar `scripts/vault.bin` con `scripts/vault_creator.py`.
- Mantener limpios `out/` y `log/` para evitar confusiones entre resultados antiguos y recientes. Los scripts escriben sobre rutas fijas, por lo que es recomendable versionar o respaldar reportes criticos.
- Al agregar nuevos casos de uso, extender `config/import_profiles.json`, registrar la vista en `AppController._on_menu_select` y crear el handler correspondiente reutilizando `TaskRunner`.
- Si se empaqueta una nueva version, validar que `AutoADA.spec` incluya cualquier dependencia adicional (hiddenimports/binaries) y ejecutar pruebas de humo en un equipo autorizado (hostname reconocido por `SecurityService`).
## 17. Glosario rapido
- **SCADA**: Supervisory Control and Data Acquisition. Las tablas 10_* y 32_* son las principales fuentes de informacion de senales.
- **HSH**: Historian (Mongo) con colecciones `groups` y `lookup_tables`. Se usa para crear y validar tags.
- **ODS / ODSTXT**: archivos operativos descargados desde servidores externos, convertidos a CSV/TXT para validaciones (unifilares, keys).
- **Jobs**: procesos de alta frecuencia para crear, eliminar o renombrar senales en SCADA.
- **PyP**: Pruebas y Puesta en marcha; pipelines de validacion antes de habilitar integraciones (itcosas v1/v2, SOE Monarch, checklist).
- **RTU/SAS**: Remote Terminal Unit / Substation Automation System, listados en el archivo `32_6.csv`.
---

Este documento resume el estado actual del proyecto Automatismo ADA segun la estructura en `c:\Users\newyo\Documents\EAFIT\Practica\AutomatismoADA`. Cualquier nueva funcionalidad deberia extender la arquitectura siguiendo los patrones descritos: vistas desacopladas, handlers con `TaskRunner`, scripts reutilizando `build_cmd`, y configuraciones centralizadas en `config/`.


















