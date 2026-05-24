# 06-06 – Plantillas Excel

AutomatizADA depende de varias **plantillas Excel** para estandarizar entradas y salidas. Esta página enumera las principales y su propósito, para que usuarias/os y desarrolladores sepan qué esperar.

---

## `templates/Checklist_V1.xlsx`

### Uso

- Plantilla base para **Pruebas PyP v1**.

### Contenido típico

- Listado de pruebas:
  - Estación.
  - Señal.
  - Descripción de prueba.
  - Campos para registrar resultados y observaciones.

### Scripts relacionados

- `scripts/itcosas_v1_ioa.py`
- `scripts/itcosas_v1_soe_local.py`
- `scripts/pyp_soe_monarch.py`
- `scripts/pyp_checklist.py`

---

## Plantilla de PyP v2 (si aplica)

Aunque el nombre exacto puede variar, suele existir una plantilla específica para PyP v2:

- Contiene columnas similares pero adaptadas a nuevos requisitos.
- Se usa en:
  - `scripts/itcosas_v2_checklist.py`
  - Otros scripts v2.

Cuando se utilice PyP v2:

- Asegurarse de usar la plantilla v2 correspondiente (no la de v1).

---

## `templates/HSH_TEMPLATE.xlsx`

### Uso

- Base para **crear tags HSH**.

### Contenido típico

- Columnas alineadas con `config/diccionario_tags.json`:
  - Nombre de tag.
  - Tipo.
  - Descripción.
  - Parámetros específicos del dominio HSH.

### Scripts relacionados

- `scripts/hsh_crear_tag.py`
- Puede influir en reportes de `validaciones_hsh.py`.

---

## `templates/ProyectoPI_EstandarSenales&TAG.xlsx`

### Uso

- Plantilla ligada a procesos de estandarización de señales y tags para proyectos PI.

### Contenido típico

- Listados de señales y tags.
- Campos que siguen estándares internos (nombres, tipos, unidades).

### Scripts relacionados

- Depende de cómo se haya integrado en flujos específicos (por ejemplo, validaciones o mapeos para proyectos PI).

---

## `templates/ScadaLoad.xlsx`

### Uso

- Base para **Jobs – Crear señales SCADA**.

### Contenido típico

- Columnas para:
  - Identificador de señal.
  - Estación.
  - Tipo.
  - Descripciones.
  - Otros datos necesarios para crear filas en tablas `10_*`, `32_*`, etc.

### Scripts relacionados

- `scripts/scan_data.py` (validación del archivo).
- `scripts/SCADA_S-A.py` (generación de cargas).

---

## Buenas prácticas para plantillas

- No modificar la estructura (nombres de columnas) sin coordinación con el equipo técnico:
  - Los scripts dependen de nombres específicos.
- Cuando se requieran cambios:
  - Documentar el cambio.
  - Actualizar el Manual de Usuario para explicar las nuevas columnas.
  - Probar los flujos que usan la plantilla en un entorno controlado.

Mantener las plantillas claras y estables es clave para minimizar errores en la entrada de datos.

