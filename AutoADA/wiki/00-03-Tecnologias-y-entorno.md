# 00-03 – Tecnologías y entorno

## Tecnologías principales

- **Lenguaje**: Python 3.x.
- **Framework de interfaz**: 
  - Tkinter/ttk para la GUI.
  - Componentes personalizados para navbar, consola embebida, status bar y diálogos.
- **Librerías de datos**:
  - `pandas`, `numpy` para manipulación de datos tabulares.
  - `openpyxl`, `pyxlsb` para lectura/escritura de archivos Excel y binarios.
- **Fechas y formatos**:
  - `python-dateutil`, `pytz`, `tzdata` para manejo de fechas y zonas horarias.
- **Seguridad y cifrado**:
  - `cryptography` (Fernet, PBKDF2) para cifrado de vaults y derivación de claves.
  - `bcrypt`, `PyNaCl` cuando aplica.
- **Conectividad remota**:
  - `paramiko`, `sshtunnel` para túneles y SSH.
  - `pymongo` para acceso a MongoDB (HSH/Historian).
  - `pyodbc` para consultas a HIS/ODBC (cuando corresponde).
- **Interfaz enriquecida**:
  - `Pillow` para manejo de imágenes e iconos.
  - `tkcalendar` para selección de fechas en ciertos módulos.

La lista completa de dependencias se encuentra en `requirements.txt` y se detalla en los anexos de la wiki.

## Arquitectura de despliegue

- **Modo desarrollo**:
  - Ejecución mediante `python main.py`.
  - Los scripts CLI se llaman con `python -u -m scripts.<modulo> ...`.
  - Los recursos (`config/`, `assets/`, `templates/`, `scripts/`) se cargan desde el árbol de código fuente.
- **Modo producción (EXE)**:
  - Empaquetado con PyInstaller (`AutomatizADAITCO.spec`, `AutomatizADAREP.spec`).
  - Se genera un único ejecutable que incluye:
    - Código Python.
    - Recursos (config, assets, templates).
    - Copias de scripts en `_runners/` para el dispatcher `--run`.
    - Vault cifrado específico para ITCO o REP.
  - Un hook (`hooks/set_cwd_runtime_hook.py`) asegura que el `cwd` se establezca en la carpeta del exe, de modo que `out/` y `log/` queden junto al ejecutable.

## Organización de datos en disco

- **AppData / staging**:
  - `%LOCALAPPDATA%\ADA-DOT\db\`  
    Dumps importados (SCADA, HSH, ODS) por empresa.
  - `%LOCALAPPDATA%\ADA-DOT\tls\`  
    Material TLS/credenciales temporales.
- **Carpeta de ejecución** (junto al exe o al proyecto en dev):
  - `out/`  
    Carpeta base para resultados:
    - `out/<EMPRESA>/SCADA|HSH|ODSTXT` con CSV/TXT convertidos.
    - Subcarpetas de resultados (`Find_key`, `Load`, `Delete`, `Validaciones_*`, `pruebas`, etc.).
  - `log/`  
    Logs por script (ej. `importar.log`, `buscar_key.log`, `consultar_rtu.log`).
- **Recursos estáticos**:
  - `config/`  
    Perfiles de importación, mapeos de tablas y servidores, diccionarios de tags.
  - `templates/`  
    Plantillas Excel usadas como base para carga/validación/reportes.
  - `assets/`  
    Iconos y recursos gráficos de la UI.

## Relaciones con sistemas externos

AutomatizADA se integra, principalmente, con:

- **SCADA**:
  - A través de dumps/tablas (10_*, 32_*, etc.) que se importan y convierten a CSV.
  - Generación de archivos de carga para jobs y señales.
- **HSH (Mongo)**:
  - Conexión mediante `pymongo` y certificados TLS propios.
  - Lectura/escritura de colecciones (`groups`, `lookup_tables`, etc.) para tags.
- **ODS / HIS**:
  - Descarga y conversión de archivos operativos a CSV/TXT para validaciones.
- **RTU/SAS**:
  - Utilización de datos SCADA convertidos para generar reportes de RTU/SAS.

Los detalles de endpoints, credenciales y parámetros se mantienen fuera del código duro y se gestionan vía:

- **Vault cifrado** (`scripts/vault.bin` o equivalentes ITCO/REP).
- **Variables de entorno** inyectadas por `AppController.secure_env()`.
- **Configuración JSON** (`config/*.json`).

## Entorno recomendado

- **Sistema operativo**: Windows 10/11 en estaciones DOT autorizadas.
- **Permisos**:
  - Acceso a las redes y servidores necesarios (SCADA, HSH, ODS/HIS).
  - Capacidad para crear y escribir en `%LOCALAPPDATA%` y en la carpeta de instalación/ejecución.
- **Python**:
  - Para entorno de desarrollo, usar la versión de Python soportada por el `requirements.txt`.
  - Se recomienda un entorno virtual para aislar dependencias.

Los detalles específicos de instalación y setup de entorno se amplían en la sección de **Desarrollo y Build**.

