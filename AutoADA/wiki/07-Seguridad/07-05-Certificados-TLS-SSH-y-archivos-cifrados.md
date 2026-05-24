# 07-05 – Certificados TLS/SSH y archivos cifrados

AutomatizADA utiliza certificados y llaves para establecer **conexiones seguras** (TLS/SSH) con sistemas externos, especialmente Mongo (HSH) y servidores remotos accesibles por SSH.

---

## Certificados para Mongo / HSH

Carpeta principal: `scripts/cifrar/` (y `scripts/cifrarREP/` en algunos entornos).

Archivos típicos:

- `mongo_ca.pem`:
  - Certificado de autoridad (CA) para validar el servidor Mongo.

- `mongo_client.pem`:
  - Certificado de cliente (incluye clave privada) para autenticarse contra Mongo.

- `key-py.pem`:
  - Archivo adicional de clave/certificado utilizado por otros scripts de cifrado o conexión.

Uso:

- `vault_manager` y `AppController.secure_env()` pueden:
  - Inyectar el contenido de estos archivos en variables de entorno:
    - `TLS_CA_CERT`
    - `TLS_CERT_KEY_PEM`
- Scripts que usan `pymongo`:
  - Configuran conexiones TLS leyendo estas variables.

En producción, estos archivos se empaquetan con el exe (en `_runners/cifrar/`), no se distribuyen sueltos.

---

## Llaves SSH y túneles

Aunque la llave privada SSH puede no estar directamente en el repositorio (por razones de seguridad), el esquema es:

- El vault contiene:
  - `ssh_user`
  - `ssh_key_pem` (contenido de la llave privada o referencia).
  - `ssh_key_passphrase` (si la llave está protegida).
  - `ssh_port`

`secure_env()`:

- Copia estos valores a:
  - `SSH_USER`
  - `SSH_KEY_PEM`
  - `SSH_KEY_PASSPHRASE`
  - `SSH_PORT`

Scripts de importación que usan `paramiko` o `sshtunnel`:

- Configuran túneles SSH usando estas variables para conectarse a:
  - Servidores SCADA.
  - Servidores de ODS/HIS u otros sistemas protegidos.

---

## Archivos cifrados de vault

Además de los certificados, el repositorio puede incluir:

- `ITCO.bin`, `REPS.bin` en `scripts/`:
  - Vaults cifrados con claves derivadas de usuario/password.
  - Contienen:
    - Credenciales.
    - Hosts.
    - Parámetros de conexión.

En ejecución:

- Se copian a una carpeta `vault/` dentro del bundle (ver `AutoADAITCO.spec` y `AutoADAREP.spec`).

---

## Packagin con PyInstaller

Archivos `.spec` (AutoADAITCO.spec, AutoADAREP.spec):

- Incluyen en `datas`:
  - `('scripts', '_runners')`:
    - Copia scripts (incluyendo certificados) a la carpeta `_runners` del ejecutable.
  - `('scripts\\ITCO.bin', 'vault')` o `('scripts\\REPS.bin', 'vault')`:
    - Copia vaults cifrados a la carpeta `vault`.
  - `('templates', 'templates')` y otros recursos.

De esta forma:

- El exe tiene internamente todo lo necesario para:
  - Conectarse de forma segura a Mongo/SCADA/HIS.
  - Desencriptar el vault correcto según ubicación.

---

## Buenas prácticas

- **No versionar** llaves privadas reales en repositorios ganados a producción:
  - Lo que está en el código debe ser un placeholder o solo aplicable a entornos de pruebas, salvo acuerdos explícitos.

- **Rotar certificados y llaves**:
  - Según políticas corporativas (caducidad, cambio de proveedores, etc.).
  - Actualizar los archivos `.pem` y los vaults asociados cuando cambien.

- **Verificar que las rutas y empaquetado son correctos**:
  - Antes de distribuir una nueva versión del exe:
    - Probar conexiones a Mongo/SCADA/HIS.
    - Revisar logs de conexión.

La seguridad de las conexiones TLS/SSH depende tanto del código como de la infraestructura y políticas externas; AutomatizADA aporta su parte gestionando bien estos archivos dentro de su ámbito.

