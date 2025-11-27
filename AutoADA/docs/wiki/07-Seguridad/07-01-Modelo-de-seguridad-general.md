# 07-01 – Modelo de seguridad general

Esta página ofrece una vista general de cómo AutoADA protege accesos y credenciales, y qué capas intervienen.

---

## Objetivos de seguridad

AutoADA busca:

- Limitar su uso a **equipos autorizados** (por ubicación/hostname).
- Evitar que usuarios finales interactúen directamente con:
  - Usuarios/contraseñas de bases de datos.
  - Certificados y llaves privadas.
  - Endpoints críticos.
- Asegurar que las credenciales:
  - Se almacenen cifradas (vault).
  - Se usen solo en memoria y via variables de entorno.
- Mantener los procesos de importación/consulta sobre canales seguros (SSH, TLS, ODBC correctamente configurado).

---

## Capas de seguridad

1. **UI (Login y restricciones por equipo)**
   - `LoginWindow`:
     - Solicita usuario/clave solo para el vault.
     - No expone credenciales de sistemas externos.
   - `SecurityService`:
     - Determina la ubicación (ITCO/REP/Desconocido) según el hostname.
     - Permite o restringe acceso a ciertas funcionalidades según el equipo.

2. **Vault cifrado**
   - `vault_manager`:
     - Almacena secretos en archivos binarios cifrados (`ITCO.bin`, `REPS.bin`, etc.).
     - Desencripta el contenido solo en memoria, a partir de usuario+clave.

3. **Variables de entorno**
   - `AppController.secure_env()`:
     - Convierte el contenido del vault en variables de entorno para scripts CLI.
     - Evita que los scripts accedan directamente al vault o a archivos sin cifrar.

4. **Conectividad segura**
   - Uso de:
     - `paramiko` / `sshtunnel` para SSH y túneles.
     - `pymongo` con TLS para Mongo (HSH).
     - `pyodbc` con drivers configurados para HIS/ODS.
   - Certificados y llaves se almacenan en archivos dedicados (`cifrar/*.pem`), empaquetados con el exe.

5. **Controles de interfaz y validaciones**
   - Formularios validan:
     - Formatos de inputs (keys, fechas, archivos).
     - Selección de empresa/dominio adecuada.
   - Los scripts y handlers:
     - Validan archivos antes de aplicar cambios (por ejemplo, `scan_data`).
     - Solicitan confirmación para operaciones críticas (aplicar cambios en HSH).

---

## Qué no hace AutoADA

Es importante entender sus límites:

- No reemplaza políticas corporativas de:
  - Gestión de identidades (AD, SSO, etc.).
  - Gestión centralizada de secrets (por ejemplo, servicios dedicados).
- No implementa por sí solo:
  - Auditoría centralizada.
  - Control de acceso a nivel de fila/columna en sistemas externos.
- Se asume que:
  - El acceso a servidores, bases y entornos está regulado por la infraestructura de la organización.
  - Solo perfiles autorizados usan AutoADA y su vault asociado.

---

## Resumen

El modelo de seguridad de AutoADA se basa en:

- Un **vault cifrado** que encapsula credenciales y parámetros sensibles.
- Un **servicio de seguridad** que restringe su uso por hostname/ubicación.
- Un **entorno de ejecución controlado** vía variables de entorno.
- El uso de **canales seguros** para conexiones remotas.

Las siguientes páginas profundizan en cada uno de estos elementos.
