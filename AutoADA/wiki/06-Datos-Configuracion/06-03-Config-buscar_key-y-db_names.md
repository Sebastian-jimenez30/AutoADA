# 06-03 – `config/buscar_key.json` y `config/db_names.json`

Los archivos `buscar_key.json` y `db_names.json` controlan cómo se realiza la búsqueda de keys en SCADA/HSH/ODS y cómo se presentan los resultados.

---

## `config/buscar_key.json`

### Propósito

Define:

- Qué **fuentes de datos** se consultan al buscar keys.
- Qué **tablas/archivos** de cada fuente se usan.
- Cómo se **mapean las columnas** de origen a nombres amigables en el reporte.

### Uso principal

Scripts:

- `scripts/buscar_key.py`
- `scripts/buscar_keys.py`

Al buscar keys:

- Estos scripts leen `buscar_key.json` para saber:
  - Qué CSV en `out/<EMPRESA>/SCADA` y `out/<EMPRESA>/HSH` analizar.
  - Qué campos extraer de cada fila coincidente.
  - En qué hoja/estructura del Excel de salida ubicar los resultados.

### Ejemplo conceptual (sin detalle real)

Una entrada típica podría describir:

- Para SCADA:
  - Tabla `10_4.csv`:
    - Columna de key (`Key`).
    - Columnas de contexto (`Name`, `pStation`, etc.).
- Para HSH:
  - `lookup_table.csv`:
    - Columna de key (`key`).
    - Columna de descripción (`description`).

`buscar_key.json` mapea estos campos para que el Excel de salida:

- Tenga encabezados amigables.
- Agrupe resultados de forma consistente.

---

## `config/db_names.json`

### Propósito

Proporciona:

- Nombres de bases/tablas en SCADA, HSH, ODS u otros sistemas externos.
- Alias legibles que se pueden mostrar en reportes o en la UI.

### Uso principal

Se usa conjuntamente con `buscar_key.json` para:

- Traducir nombres internos de tablas/bases a nombres legibles.
- Hacer que los reportes de búsqueda sean más entendibles para usuarios que no conocen los nombres técnicos exactos.

Por ejemplo:

- `10_4` → “Tabla de estados SCADA”.
- `lookup_table` → “Tabla de lookup HSH”.

---

## Impacto de modificar estos archivos

Cambios en `buscar_key.json`:

- Pueden afectar:
  - Qué tablas se consultan.
  - Qué columnas aparecen en `Find_Key.xlsx`.
- Si se elimina o renombra una tabla:
  - Los scripts de búsqueda pueden fallar al no encontrar CSV o columnas esperadas.

Cambios en `db_names.json`:

- Afectan principalmente:
  - Etiquetas y nombres que se muestran en reportes.
- Menos riesgosos desde el punto de vista de ejecución, pero pueden confundir si no se mantienen coherentes.

Recomendaciones:

- Probar la funcionalidad de búsqueda de keys después de cualquier cambio.
- Documentar internamente qué tablas/columnas se agregan o se retiran.

---

## Buenas prácticas

- Mantener `buscar_key.json` y `db_names.json` alineados:
  - Si se añade una nueva tabla a `buscar_key.json`, asegurarse de que tenga un alias apropiado en `db_names.json` si se usará en reportes.
- No duplicar definiciones:
  - Centralizar mapeos comunes en un solo lugar para evitar inconsistencias.

Estos archivos son una de las piezas que hacen que la búsqueda de keys sea flexible y fácil de mantener sin tocar directamente el código de los scripts.

