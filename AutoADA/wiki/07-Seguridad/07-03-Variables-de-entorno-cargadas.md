# 07-03 – Variables de entorno cargadas desde el vault

Esta página resume las **variables de entorno** que AutomatizADA carga a partir del vault y cómo las utilizan los scripts CLI.

---

## ¿Por qué usar variables de entorno?

En lugar de que los scripts lean directamente el vault o archivos con secretos, AutomatizADA:

- Desencripta el vault en la capa de aplicación (`AppController`).
- Extrae los valores necesarios.
- Los pone en variables de entorno.
- Lanza los scripts con un `env` enriquecido.

Así los scripts:

- Solo conocen los valores que necesitan (usuario, contraseña, hosts, etc.).
- No necesitan saber cómo se manejan vaults ni claves.

---

## `AppController.secure_env()`

Función clave que:

- Parte de `os.environ.copy()`.
- Inyecta variables desde el dict `vault`.
- Añade ajustes generales para ejecución CLI.
- Devuelve un `env` que se pasa a `TaskRunner.run_subprocess`.

Se suele invocar:

- Al iniciar la app (para poblar variables globales).
- Antes de lanzar cada pipeline (para asegurar consistencia).

---

## Variables relacionadas con Mongo / HSH

- `MONGO_USER`
- `MONGO_PASS`
- `MONGO_PORT`
- `REPLICA_SET`

Uso:

- Scripts que necesitan conectarse a MongoDB (HSH), por ejemplo:
  - `test_mongo.py`
  - `validaciones_hsh.py`
  - `hsh_crear_tag.py`
  - etc.

---

## Variables relacionadas con SSH / túneles

- `SSH_USER`
- `SSH_KEY_PEM`
- `SSH_KEY_PASSPHRASE`
- `SSH_PORT`

Uso:

- Scripts que establecen túneles SSH hacia servidores remotos para:
  - Importar datos SCADA.
  - Importar ODS/HIS cuando hace falta.
- Pueden utilizar `paramiko` o `sshtunnel` leyendo estas variables.

`SSH_KEY_PEM` suele contener **el contenido de la llave** (no solo una ruta), especialmente en entornos empaquetados.

---

## Variables para hosts SCADA/HIS

- `SCA_HOSTS`
  - Lista (normalmente separada por comas) de hosts de SCADA.

- `HIS_HOSTS`
  - Lista de hosts HIS.

- `HIS_PRIMARY`, `HIS_SECONDARY`
  - Hosts derivados de `HIS_HOSTS` (primario y secundario).

Uso:

- Scripts de importación y consulta que necesiten saber a qué host ir para SCADA/HIS.

---

## Variables para TLS (Mongo y otros)

- `TLS_CERT_KEY_PEM`
- `TLS_CA_CERT`

Uso:

- Configurar conexiones TLS a MongoDB:
  - Certificado de cliente.
  - Certificado de autoridad.

Si estas variables no están en el vault, `secure_env` intenta:

- Leer los archivos `.pem` empaquetados:
  - `scripts/_runners/cifrar/mongo_client.pem`.
  - `scripts/_runners/cifrar/mongo_ca.pem`.
- Insertar su contenido en las variables.

---

## Variables para ODBC / HIS

- `ODBC_DRIVER`
- `ODBC_DB`
- `ODBC_USER`
- `ODBC_PASS`
- `ODBC_PORT` (si no está, se establece un valor por defecto, por ejemplo `5432`).

Uso:

- Scripts que se conectan a HIS u otras bases via ODBC:
  - Por ejemplo, `test_pi_query.py` o `import_his_soe.py`, dependiendo de la implementación.

---

## Variables para PI (si aplica)

- `USER_PI`
- `PASS_PI`

Uso:

- Scripts que requieren autenticarse en servicios PI.

---

## Variables de runtime adicionales

- `ADA_BASE_DIR`
  - Raíz de trabajo (carpeta donde viven `out/` y `log/`).

- `PYTHONUNBUFFERED=1`
  - Fuerza stdout/stderr sin buffer, útil para ver logs en tiempo real.

- `PYTHONIOENCODING=utf-8`
  - Asegura decodificación consistente de salida en UTF-8.

- `FORCE_COLOR=1`
  - Puede influir en scripts que pintan la salida (opcional).

---

## Consideraciones de seguridad

- Estas variables existen mientras se ejecuta AutomatizADA y sus subprocesos.
- No deben escribirse a disco en claro (más allá de lo que los scripts necesiten).
- Los logs no deben registrar credenciales completas; solo mensajes genéricos y, en lo posible, hostnames sin secretos.

Si se detecta que un script registra valores sensibles, es necesario ajustarlo para evitar fugas de información.

