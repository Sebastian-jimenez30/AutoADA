# 07-02 – Vault cifrado y esquemas de clave

AutoADA usa un **vault cifrado** para almacenar credenciales y parámetros sensibles. Esta página explica cómo funciona ese vault y cómo se derivan las claves.

---

## ¿Qué es el vault?

Es un archivo binario cifrado (por ejemplo, `ITCO.bin`, `REPS.bin`) que contiene un JSON con:

- Usuarios y contraseñas para:
  - MongoDB (HSH).
  - HIS/ODBC.
  - Otros servicios externos.
- Parámetros de conexión:
  - Hosts.
  - Puertos.
  - Nombres de bases.
- Rutas o contenidos de llaves y certificados (TLS/SSH), cuando aplica.

Este archivo:

- Se distribuye junto al ejecutable.
- Nunca se lee directamente por los scripts.
- Solo se desencripta a través de `vault_manager`.

---

## Esquema de cifrado

Implementado en `scripts/vault_manager.py`:

- **Algoritmo**: Fernet (simétrico, basado en AES).
- **Derivación de clave**:
  - Uso de `PBKDF2-HMAC (SHA256)` con:
    - `username` y `password` provistos en el login.
    - `salt` derivado del usuario (`APP_SALT_PREFIX + username`).
    - Número de iteraciones elevado (ej. 200k) para endurecer la derivación.
- **Clave legacy**:
  - Para compatibilidad con versiones anteriores:
    - Existe un esquema legacy basado solo en el password (padding/truncado a 32 bytes).

El flujo de desencriptado es:

1. Construir la clave con `username + password`.
2. Intentar desencriptar el vault.
3. Si falla, intentar con la clave legacy (solo password).
4. Si ambos fallan, informar al usuario (“Clave incorrecta o vault corrupto”).

---

## Dónde se ubica el vault

`vault_manager` resuelve rutas considerando el entorno:

- En ejecutable (PyInstaller):
  - Vaults suelen copiarse a una carpeta `vault/` dentro del bundle.
  - Se resuelven usando `_bundle_root()` (`sys._MEIPASS`) + `vault/<nombre>.bin`.

- En desarrollo:
  - Vaults viven en `scripts/`:
    - `scripts/vault.bin`.
    - `scripts/ITCO.bin`.
    - `scripts/REPS.bin`.

Funciones clave:

- `_resolve_default_vault_path()`:
  - Busca `vault/vault.bin` o `scripts/vault.bin`.
- `resolve_named_vault_path(filename)`:
  - Busca un archivo de vault específico (`ITCO.bin`, `REPS.bin`).

`LoginWindow` suele usar `resolve_named_vault_path` según la ubicación detectada.

---

## Lógica de `load_vault_from_credentials`

Firma simplificada:

```python
load_vault_from_credentials(
    username: str,
    password: str,
    vault_path: Optional[str] = None,
    require_authorized: bool = False,
    required_keys: Optional[Iterable[str]] = None,
) -> Dict[str, Any]
```

Pasos:

1. Determinar la ruta del vault (`vault_path` o default).
2. Intentar desencriptar con esquema **nuevo** (username+password).
3. Si falla, intentar esquema **legacy** (password solo).
4. Cargar el JSON resultante y verificar que sea un dict.
5. Si `required_keys` está definido, validar que todas estén presentes.

Si algo falla:

- Se lanza una excepción clara que el login captura y muestra al usuario.

---

## Relación con el login

- `LoginWindow`:
  - Pide `usuario` y `clave`.
  - Usa `SecurityService` para sugerir el nombre de vault:
    - `ITCO.bin` si la máquina está en ITCO.
    - `REPS.bin` si está en REP.
  - Llama a `load_vault_from_credentials`:
    - Si tiene éxito:
      - Entrega el dict de vault a `AppController`.
    - Si falla:
      - Muestra “Acceso denegado”.

La aplicación **nunca guarda** el password del usuario; solo lo usa para derivar la clave y luego lo descarta.

---

## Regeneración del vault

Scripts como:

- `scripts/vault_creator.py`
- `scripts/vault_creatorREP.py`

Permiten:

- Crear o actualizar vaults (`ITCO.bin`, `REPS.bin`) a partir de:
  - Un JSON de configuración con secretos.
  - Un username/password para fijar el esquema de cifrado.

Se recomienda que esta tarea la realice personal autorizado, dado que implica manejar credenciales en claro antes de cifrarlas.

---

## Recomendaciones de operación

- No distribuir vaults por canales inseguros (correo sin cifrar, compartidos sin control).
- Cambiar el vault y/o sus claves cuando:
  - Cambien credenciales de sistemas externos.
  - Haya sospecha de compromiso.
- Mantener una relación clara entre:
  - Ubicación (ITCO/REP).
  - Vault correspondiente (`ITCO.bin`/`REPS.bin`).

El vault es el corazón del manejo de credenciales en AutoADA; protegerlo adecuadamente es fundamental.

