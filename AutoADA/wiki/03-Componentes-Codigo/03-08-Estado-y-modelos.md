# 03-08 – Estado y modelos

Actualmente, AutomatizADA utiliza un modelo de estado relativamente simple, pero está preparado para crecer con nuevas necesidades. Esta página describe el estado global y posibles evoluciones.

---

## `AppState` (state/app_state.py)

Definición:

- Dataclass `AppState` con campos:
  - `usuario: Optional[str]`
  - `rol: Optional[str]`
  - `ubicacion: str` (por defecto `"Desconocido"`)
  - `empresa_activa: Optional[str]`
  - `dominio_activo: Optional[str]`

Responsabilidades:

- Guardar información básica de contexto:
  - Quién está usando la aplicación.
  - En qué entorno (ITCO/REP/Desconocido).
  - Qué empresa y dominio están actualmente seleccionados (si aplica).

Uso:

- `AppController` instancia y mantiene un `AppState`.
- Vistas y handlers pueden consultar o actualizar `empresa_activa`/`dominio_activo` según las selecciones del usuario.

---

## Contexto operativo extendido

Aparte de `AppState`, el contexto operativo vive en:

- Atributos de `AppController`:
  - Referencias a vistas actuales (`marco_actual`).
  - Rutas de archivos seleccionados (por ejemplo, `archivo_excel_buscar_keys`, `archivos_unifilares`).
  - Variables y widgets asociados a formularios (combos, checkboxes, botones).
- Variables de entorno:
  - Povistas por `secure_env` (credenciales, hostnames, rutas TLS, etc.).

Aunque no son “modelos” en el sentido clásico (como en un patrón MVC estricto), conforman el conjunto de estado de la aplicación.

---

## Posibles extensiones de modelos

Si el proyecto crece, podría ser útil introducir modelos adicionales, por ejemplo:

- **Modelos de configuración en memoria**:
  - Abstraer `config/*.json` en clases que expongan métodos específicos (por ejemplo, `ImportProfile`, `ServerConfig`).
- **Modelos de dominio**:
  - Representar entidades como:
    - Señal SCADA.
    - Tag HSH.
    - Job.
    - Unifilar.
  - Con métodos para validar, comparar, transformar.
- **Modelos de resultados**:
  - Estructuras que representen reportes generados, con metadatos (empresa, fecha, tipo, ruta de archivo).

Estas extensiones podrían:

- Mejorar la legibilidad del código.
- Facilitar pruebas unitarias más estructuradas.
- Permitir nuevas vistas que exploten más información sin depender directamente de archivos.

---

## Recomendaciones al introducir nuevos modelos

- Mantener los modelos **independientes de la UI**:
  - Que no dependan de widgets Tkinter.
- Reducir el acoplamiento con scripts CLI:
  - Idealmente, los modelos deberían conocer formatos de archivos, pero no cómo se ejecutan scripts externos.
- Usar dataclasses o `NamedTuple` cuando sea apropiado:
  - Facilita la construcción y la comparación en pruebas.

---

## Resumen

- El estado central de la aplicación hoy está en `AppState` y en atributos del `AppController`.
- La arquitectura permite introducir modelos más ricos si la complejidad del dominio lo exige.

Entender cómo se maneja el estado actual es importante para evitar duplicidades y mantener la coherencia cuando se extiendan funcionalidades.

