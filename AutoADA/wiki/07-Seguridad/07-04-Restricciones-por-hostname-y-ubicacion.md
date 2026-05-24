# 07-04 – Restricciones por hostname y ubicación

AutomatizADA no está pensado para ejecutarse en cualquier equipo: aplica restricciones basadas en el **hostname** de la máquina para determinar la “ubicación” y ajustar qué se permite.

---

## Ubicaciones soportadas

`SecurityService` define un tipo `Ubicacion` con posibles valores:

- `"ITCO"`
- `"REP"`
- `"Desconocido"`

La lógica de detección se basa en el hostname:

- Si el hostname comienza con ciertos prefijos (por ejemplo, `itco1`, `tra1`, `isa1cct5_p`, `isa1ccwx_p`, etc.), se considera `"ITCO"`.
- Si comienza con `rep1`, `rep2`, etc., se considera `"REP"`.
- En otros casos, `"Desconocido"`.

Esta lista de prefijos puede ajustarse según la infraestructura real.

---

## ¿Qué implica la ubicación?

### 1. Selección de vault

- `ITCO`:
  - Suele usar `ITCO.bin` como vault.
- `REP`:
  - Suele usar `REPS.bin`.
- `Desconocido`:
  - Puede no tener un vault asociado, o usar un vault genérico solo para pruebas.

`LoginWindow` utiliza la ubicación para sugerir el nombre de vault a abrir.

### 2. Empresas permitidas

Método `empresas_permitidas(ubicacion)`:

- `ITCO` → `["ITCO", "TRA"]`
- `REP` → `["REPS", "REPP"]`
- `Desconocido` → puede devolver todas (`["ITCO","TRA","REPS","REPP"]`) o una lista restringida según configuración.

Esto afecta:

- Qué empresas aparecen en combos de la UI.
- Qué empresas se consideran en la actualización global de datos.

### 3. Empresas para Jobs

Método `empresas_para_jobs(ubicacion)`:

- `ITCO` → `["ITCO"]`
- `REP` → `["REPS"]`
- `Desconocido` → podría devolver `["ITCO"]` u otra combinación limitada.

Controla en qué empresas se permiten Jobs desde esa ubicación.

---

## `_guard_location` en `AppController`

`AppController` ejecuta un método interno (`_guard_location`) que:

- Usa `SecurityService` para detectar la ubicación al inicio.
- Puede:
  - Ajustar internamente `state.ubicacion`.
  - Cerrar la aplicación si la ubicación no está autorizada.

Esto evita que AutomatizADA se ejecute “normalmente” en equipos desconocidos.

---

## Escenarios típicos

- **Equipo de ITCO**:
  - Hostname con prefijo reconocido.
  - Ubicación: `ITCO`.
  - Vault sugerido: `ITCO.bin`.
  - Empresas en UI: ITCO, TRA.
  - Jobs: solo para ITCO.

- **Equipo de REP**:
  - Hostname con prefijo `rep1`/`rep2`.
  - Ubicación: `REP`.
  - Vault sugerido: `REPS.bin`.
  - Empresas en UI: REPS, REPP.
  - Jobs: solo para REPS.

- **Equipo desconocido**:
  - Hostname no coincide con ninguna regla.
  - Ubicación: `Desconocido`.
  - Comportamiento:
    - Puede permitirse solo modo demo o lectura.
    - Puede bloquearse completamente (dependiendo de `_guard_location`).

---

## Ajustes y mantenimiento

Si la infraestructura cambia (nuevos hostnames, equipos renombrados):

- Es necesario actualizar:
  - La lógica de prefijos en `SecurityService`.
  - Opcionalmente, reglas de empresas permitidas.

Se recomienda:

- Documentar internamente cualquier cambio en estas reglas.
- Validar que los equipos de pruebas y producción se detectan correctamente tras los ajustes.

Estas restricciones ayudan a asegurar que AutomatizADA solo se use en entornos controlados y con la configuración adecuada.

