# 06-04 – Diccionario de tags y plantillas HSH

Esta página resume los archivos de configuración y plantillas que giran alrededor de **tags HSH**: diccionarios, estructuras de datos y plantillas Excel.

---

## `config/diccionario_tags.json`

### Propósito

Contiene **metadatos de tags HSH**, por ejemplo:

- Tipos de tags.
- Categorías.
- Campos obligatorios u opcionales.
- Mapeos entre tipos lógicos y campos técnicos en la base HSH.

Esto ayuda a:

- Validar que los tags cumplan reglas de negocio.
- Generar plantillas y reportes con información consistente.

### Uso típico

Scripts:

- `scripts/hsh_crear_tag.py`
- `scripts/hsh_cambiar_key.py`
- `scripts/hsh_eliminar_tag.py`
- `scripts/validaciones_hsh.py`

Estos scripts pueden usar el diccionario para:

- Comprobar que los campos requeridos están presentes.
- Validar combinaciones de valores.
- Decidir cómo presentar u organizar tags en los reportes.

---

## Plantilla `templates/HSH_TEMPLATE.xlsx`

### Propósito

Sirve como base para:

- Cargar tags nuevos en HSH (crear).
- Estandarizar los campos que se deben rellenar al proponer tags.

### Contenido típico

A modo conceptual, incluye columnas como:

- Nombre del tag.
- Tipo de señal.
- Descripción.
- Parámetros adicionales (unidades, límites, etc.).
- Campos específicos que se mapearán a `groups`, `lookup_tables` u otras estructuras internas.

### Uso recomendado

- Antes de correr el módulo **Crear Tag HSH**:
  - Asegúrate de que el Excel sigue esta plantilla.
- No añadas ni elimines columnas sin coordinar con el equipo técnico:
  - Los scripts esperan ciertos nombres de columnas.

---

## Relación entre diccionario y plantilla

- `diccionario_tags.json` describe de forma estructurada:
  - Qué campos existen.
  - Qué significan.
  - Qué restricciones tienen.
- `HSH_TEMPLATE.xlsx` ofrece una interfaz para:
  - Que las usuarias/os llenen esos campos.
  - Mantener un formato estándar.

Los scripts se apoyan en ambos:

- Leen el Excel.
- Verifican que campos y valores coincidan con lo definido en el diccionario.
- Construyen operaciones de creación/cambio/eliminación de tags en HSH.

---

## Buenas prácticas al modificar estos archivos

- Cambios en `diccionario_tags.json`:
  - Hacerlos con cuidado y en coordinación con el equipo que mantiene HSH.
  - Revisar cómo afectarán a:
    - Validaciones.
    - Reportes.
    - Cambios masivos de tags.

- Cambios en `HSH_TEMPLATE.xlsx`:
  - Documentar el cambio y actualizar el manual de usuario si:
    - Se agregan nuevas columnas.
    - Se renombra alguna columna.
  - Probar el flujo de creación de tags con un pequeño conjunto de datos antes de usarlo en producción.

Una gestión cuidadosa de estos archivos reduce errores y mantiene coherente la administración de tags HSH en AutoADA.

