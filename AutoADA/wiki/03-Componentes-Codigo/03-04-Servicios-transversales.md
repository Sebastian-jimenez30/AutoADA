# 03-04 – Servicios transversales

Los servicios encapsulan lógica que es compartida por distintas partes de la aplicación pero que no pertenece directamente a la UI ni a los scripts CLI. Aquí se describen los principales.

---

## `SecurityService` (services/security_service.py)

Responsabilidades:

- **Detección de ubicación**:
  - Método `detectar_ubicacion()`:
    - Obtiene el hostname del equipo.
    - Aplica reglas de prefijos para clasificar la ubicación en:
      - `"ITCO"`, `"REP"` o `"Desconocido"`.
    - Maneja excepciones devolviendo `"Desconocido"` por defecto.
- **Resolución de vault por ubicación**:
  - Método `resolve_vault_filename(ubicacion)`:
    - Devuelve el nombre sugerido de archivo de vault según ubicación (ej. `ITCO.bin`, `REPS.bin`).
- **Restricción de empresas**:
  - Método `empresas_permitidas(ubicacion)`:
    - Devuelve la lista de empresas que el usuario puede ver/usar según su ubicación.
  - Método `empresas_para_jobs(ubicacion)`:
    - Devuelve las empresas válidas para operaciones de Jobs en esa ubicación.

Uso:

- `LoginWindow` utiliza `detectar_ubicacion` y `resolve_vault_filename` para sugerir el vault correcto.
- `AppController` usa `empresas_permitidas` y `empresas_para_jobs` para poblar combos y vistas.
- `_guard_location` se apoya en la ubicación detectada para validar si la ejecución está permitida.

---

## `ServerResolver` (services/server_resolver.py)

Responsabilidades:

- **Resolver servidores por empresa/dominio**:
  - Inicializa leyendo `config/servers.json` mediante una función de ayuda que respeta el entorno (dev/exe).
  - Mantiene diccionarios internos:
    - `_empresa_claves`: mapea nombres de empresa a claves numéricas.
    - `_opciones_dominio`: mapea dominios (QA, CC, etc.) a claves.
  - Método `generar_server(empresa, dominio)`:
    - Usa las claves para indexar en `servers.json` y recuperar el hostname.
    - Devuelve `None` si no encuentra combinación válida.
- **Exponer vistas solo lectura para la UI**:
  - Métodos `empresa_claves_view()` y `opciones_dominio_view()`:
    - Devuelven `MappingProxyType` (diccionarios inmutables) con los mapeos de empresa y dominio.

Uso:

- `AppController` obtiene estas vistas para:
  - Poblar combos de empresa/dominio.
  - Resolver servidores antes de ejecutar `importar_all`.
- `handlers.actualizar_datos` y otros handlers usan `generar_server` para construir comandos que requieran hostnames correctos.

---

## `vault_manager` (scripts/vault_manager.py) – Servicio de credenciales

Aunque reside en `scripts/`, actúa conceptualmente como un servicio transversal.

Responsabilidades:

- **Resolución de ruta del vault**:
  - `_bundle_root()`:
    - En ejecutable: `sys._MEIPASS`.
    - En dev: carpeta de `vault_manager.py`.
  - `_resolve_default_vault_path()`:
    - Busca `vault/vault.bin` en el bundle.
    - O `scripts/vault.bin` en desarrollo.
  - `resolve_named_vault_path(filename)`:
    - Busca un vault específico (por ejemplo, `ITCO.bin` o `REPS.bin`) en rutas análogas.

- **Derivación de claves**:
  - `_derive_key_from_username_password(username, password)`:
    - Usa PBKDF2-HMAC (SHA256) con salt derivado del usuario.
    - Genera una clave de 32 bytes en formato `urlsafe_b64` para Fernet.
  - `_legacy_key_from_password(password)`:
    - Implementación legacy (padding/truncado a 32 bytes).

- **Carga y desencriptado**:
  - `_load_and_decrypt(path, key)`:
    - Usa Fernet para desencriptar el vault y devolver un dict JSON.
  - `load_vault_from_credentials(username, password, vault_path, ...)`:
    - Intenta primero con el esquema nuevo (username+password).
    - Si falla, intenta esquema legacy (solo password).
    - Valida la presencia de claves requeridas si se especifican.

Uso:

- `LoginWindow` usa `resolve_named_vault_path` y `load_vault_from_credentials` para obtener el vault desencriptado.
- `AppController` recibe el dict de vault y lo utiliza en `secure_env` para construir el entorno de ejecución.

---

## Otros servicios potenciales

Aunque actualmente el repositorio se centra en los servicios anteriores, la arquitectura permite agregar fácilmente nuevos servicios para:

- Auditar eventos significativos (por ejemplo, un `AuditService`).
- Gestionar preferencias de usuario o estado persistente ligero.
- Encapsular lógica de acceso a otros sistemas externos.

Al diseñar nuevos servicios, se recomienda:

- Mantenerlos desacoplados de la UI y de los scripts CLI.
- Definir interfaces claras (métodos bien nombrados).
- Evitar dependencias circulares con controladores y handlers.

---

## Resumen

- `SecurityService` controla ubicación, empresas permitidas y selección de vault.
- `ServerResolver` traduce empresa/dominio a hostnames para importaciones y otros procesos.
- `vault_manager` centraliza el manejo de vaults cifrados.

Estos servicios permiten que el resto de la aplicación trabaje con una **visión coherente del entorno** sin reimplementar lógica de seguridad y resolución de servidores en cada módulo.

