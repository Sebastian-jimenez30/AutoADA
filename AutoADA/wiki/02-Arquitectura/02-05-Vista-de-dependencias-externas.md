# 02-05 – Vista de dependencias externas

AutomatizADA interactúa con varios **sistemas y librerías externas**. Esta página resume cuáles son, para qué se usan y cómo se integran.

---

## Sistemas externos de datos

### SCADA

- Origen principal de tablas de señales, jobs, estados, eventos.
- AutomatizADA:
  - Importa dumps/tablas SCADA mediante scripts de importación.
  - Convierte esos datos a CSV (`10_*`, `32_*`, etc.) bajo `out/<EMPRESA>/SCADA`.
  - Usa esos CSV para:
    - Búsqueda de keys.
    - Jobs (crear, eliminar, renombrar señales).
    - Validaciones de unifilares.
    - Pruebas PyP.
    - Consultas RTU/SAS.

### HSH / Historian (Mongo)

- Sistema de historización de tags.
- AutomatizADA:
  - Conecta a MongoDB usando `pymongo` a través de túneles/SSL según corresponda.
  - Lee y, en ciertos procesos, modifica colecciones como `groups` o `lookup_tables`.
  - Utiliza certificados (`mongo_ca.pem`, `mongo_client.pem`) distribuidos cifrados.

### ODS / HIS

- Sistemas de datos operativos e históricos.
- AutomatizADA:
  - Importa archivos (ODS/HIS) mediante scripts dedicados.
  - Convierte esos archivos a formatos de trabajo (CSV/TXT).
  - Usa esos datos en:
    - Validación de unifilares.
    - Pruebas PyP.

### RTU/SAS

- Equipos de campo y sistemas de automatización de subestaciones.
- AutomatizADA:
  - No se conecta directamente a RTU/SAS en tiempo real.
  - Utiliza datos SCADA ya descargados para generar reportes de RTU/SAS (por ejemplo, mapeos de señales).

---

## Librerías de conectividad y seguridad

### MongoDB / Historian

- `pymongo`:
  - Cliente para MongoDB.
  - Usado en scripts como `test_mongo.py`, validaciones HSH y otros procesos que consultan/actualizan Mongo.
- Certificados TLS:
  - Archivo de CA (`mongo_ca.pem`) y certificado de cliente (`mongo_client.pem`).
  - Rutas se inyectan vía variables de entorno (`TLS_CA_CERT`, `TLS_CERT_KEY_PEM`).

### ODBC / HIS

- `pyodbc`:
  - Permite conectarse a fuentes ODBC (por ejemplo, HIS).
  - La configuración (driver, base de datos, usuario, contraseña, puerto) se extrae del vault y se expone vía variables de entorno (`ODBC_DRIVER`, `ODBC_DB`, etc.).

### SSH / túneles

- `paramiko` y `sshtunnel`:
  - Facilitan la creación de túneles SSH hacia servidores remotos para importar datos.
  - Credenciales y rutas a llaves privadas se obtienen del vault (`SSH_USER`, `SSH_KEY_PEM`, `SSH_KEY_PASSPHRASE`, `SSH_PORT`).

---

## Librerías de datos y formatos

- `pandas`, `numpy`:
  - Manipulación de tablas, filtrado, agregaciones y transformaciones.
  - Base de la mayoría de scripts de conversión y análisis.
- `openpyxl`, `pyxlsb`:
  - Lectura y escritura de archivos Excel (XLSX, XLSB).
  - Uso intensivo en:
    - Plantillas de Jobs.
    - Plantillas HSH.
    - Checklists PyP.
    - Reportes de resultados.
- `tkcalendar`:
  - Widgets de fecha en la UI para procesos que requieren seleccionar días/intervalos.

---

## Librerías de seguridad y cifrado

- `cryptography`:
  - Implementa Fernet para cifrado simétrico del vault.
  - Usa PBKDF2-HMAC (SHA256) para derivar claves a partir de usuario/contraseña.
- `bcrypt`, `PyNaCl`:
  - Pueden participar en operaciones complementarias de seguridad cuando se requiera (por ejemplo, hashing).

El diseño busca que las credenciales nunca se almacenen en texto plano dentro del código ni de la carpeta del exe.

---

## Librerías de interfaz y sistema

- `tkinter` / `ttk`:
  - Base de la GUI.
  - Se combina con estilos personalizados definidos en `ui/theme.py`.
- `Pillow (PIL)`:
  - Carga y escalado de iconos/logos usados en la barra de título y navbar.
- Utilidades de sistema (`subprocess`, etc.):
  - Ejecución de scripts CLI.
  - Apertura de archivos/carpeta (`utils.shell` → `os.startfile`, `open`, `xdg-open`).

---

## Dependencias empaquetadas con PyInstaller

Los archivos de especificación (`AutomatizADAITCO.spec`, `AutomatizADAREP.spec`) se encargan de:

- Incluir:
  - `assets/`, `config/`, `db/`, `scripts/`, `templates/`.
  - Archivos binarios de vault (`ITCO.bin`, `REPS.bin`) en la carpeta `vault/` del bundle.
- Marcar como `hiddenimports`:
  - Paquetes que PyInstaller no detecta automáticamente (`pandas`, `numpy`, `openpyxl`, `tkcalendar`, `pyxlsb`, `pymongo`, `pyodbc`, etc.).
- Recoger librerías nativas necesarias (por ejemplo, `.pyd`/`.dll` de `pyodbc`).

Esto asegura que el ejecutable resultante tenga todo lo necesario para funcionar en estaciones de trabajo autorizadas sin instalar manualmente cada dependencia.

---

## Resumen

AutomatizADA se apoya en un conjunto de sistemas y librerías externas para:

- Obtener datos (SCADA, HSH, ODS/HIS).
- Manipularlos (pandas, numpy, Excel).
- Proteger accesos (cifrado, TLS, SSH).
- Presentarlos en una interfaz amigable (Tkinter, Pillow).

Entender estas dependencias ayuda a:

- Diagnosticar problemas de conectividad o compatibilidad.
- Planear actualizaciones (por ejemplo, versiones de Mongo, drivers ODBC).
- Evaluar impactos de cambios en la infraestructura sobre AutomatizADA.

