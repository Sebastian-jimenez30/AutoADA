# 04-02 – Buscar Key / Keys

Este pipeline permite buscar una o múltiples **keys** en distintas fuentes de datos (SCADA, HSH, ODS) y generar un Excel consolidado con los resultados.

Hay dos variantes:

- **Buscar Key**: búsqueda manual de una cadena o patrón.
- **Buscar Keys**: búsqueda masiva a partir de un archivo Excel.

---

## Objetivo del flujo

- Localizar rápidamente claves en:
  - Tablas SCADA convertidas.
  - Datos HSH convertidos.
  - Archivos ODS/ODSTXT convertidos.
- Presentar un **reporte único** que indique:
  - Dónde aparece cada key.
  - Información asociada (campo, tabla, base, descripciones, según configuración).

---

## Punto de entrada en la UI

- Vista: `Buscar Key / Buscar Keys` (`interfaces/marco_buscar_key.py`).
- Secciones principales:
  - Modo 1: **Buscar una Key** (entrada manual).
  - Modo 2: **Buscar Keys desde archivo** (Excel).
- Elementos comunes:
  - Combo de empresa.
  - Checkbox “Actualizar BD” (cuando procede).
  - Botones para lanzar búsqueda.
  - Consola embebida.

---

## Entradas necesarias

### Datos locales

- CSV convertidos en:
  - `out/<EMPRESA>/SCADA`.
  - `out/<EMPRESA>/HSH` (por ejemplo, `groups.csv`, `lookup_table.csv`).
  - `out/<EMPRESA>/ODSTXT` (TXT/CSV).

La disponibilidad se verifica con `utils.data_checks.find_mode_data_ready(base_dir, empresa)`:

- Si faltan datos:
  - Se fuerza o sugiere activar “Actualizar BD”.

### Parámetros de UI

- **Empresa**:
  - Debe seleccionarse antes de ejecutar cualquier búsqueda.
- **Modo manual**:
  - Cadena de key(s), por ejemplo:
    - `12345.67`
    - `12345.%` (permite comodines `%`).
  - Se separan por comas para múltiples keys.
- **Modo archivo**:
  - Excel que contenga las keys a buscar (por ejemplo, en la columna A).
- **Actualizar BD** (opcional):
  - Si está activo, se ejecutará una actualización de datos para la empresa antes de la búsqueda.

---

## Validaciones previas

### Validación de keys (modo manual)

- Función: `handlers/buscar_key/common._validar_keys(cadena)`.
- Regla:
  - Se consideran válidas las keys que:
    - Contienen `%`, o
    - Tienen 8 caracteres, con formato `#####.##`, y los segmentos a ambos lados del punto son numéricos.
  - Las demás se marcan como inválidas.
- Si hay keys inválidas:
  - Se informa al usuario.
  - Puede impedirse la ejecución o limitarse a las válidas (según configuración/handler).

### Disponibilidad de datos

- `find_mode_data_ready` devuelve:
  - `ok`: si SCADA, HSH y ODSTXT cumplen mínimos.
  - `details`: qué dataset falta (SCADA/HSH/ODSTXT/OUT).
- Si `ok` es `False`:
  - La UI puede:
    - Forzar “Actualizar BD” a `True`.
    - Bloquear la búsqueda hasta que se actualicen los datos.

---

## Pasos del pipeline – Modo con actualización de datos

Cuando se marca “Actualizar BD”:

1. **Resolución de servidor**:
   - Usa `ServerResolver.generar_server(empresa, dominio)` (usualmente dominio “CC”).
2. **Importación**:
   - Comando:
     - `scripts.importar_all servidor empresa "sca,hsh,ods" --usecase buscar_keys`.
3. **Conversión**:
   - Comando:
     - `scripts.Convertir_all empresa "Buscar_keys" --only sca,hsh,ods,ods_csv`.
4. **Actualización de estado**:
   - Se recalcula la “última actualización” de datos.

Tras estos pasos, el flujo continúa con la búsqueda (modo manual o archivo).

---

## Pasos del pipeline – Búsqueda manual (Buscar Key)

1. **Entrada de key(s)**:
   - Usuario ingresa una o varias keys separadas por comas.
2. **Validación**:
   - `_validar_keys` separa keys válidas e inválidas.
   - Si todas son inválidas → error.
3. **Ejecución del script**:
   - Se construye el comando:
     - `scripts.buscar_key` con:
       - Empresa.
       - Lista de keys válidas (como argumento o mediante archivo temporal según implementación).
   - `TaskRunner` lanza el subproceso.
4. **Procesamiento interno (scripts/buscar_key.py)**:
   - Lee configuraciones de `config/buscar_key.json` y `config/db_names.json`.
   - Consulta los CSV convertidos de SCADA/HSH/ODS.
   - Aplica filtros y mapeos configurados.
   - Genera el reporte:
     - `out/Find_key/Find_Key.xlsx`.
5. **Salida**:
   - El handler:
     - Rehabilita el botón de búsqueda.
     - Muestra un diálogo de éxito apuntando a `Find_Key.xlsx`.
     - Escribe resumen en consola (número de coincidencias, etc.).

---

## Pasos del pipeline – Búsqueda masiva (Buscar Keys desde Excel)

1. **Selección de archivo**:
   - Usando el selector de archivos, la usuaria/o elige un Excel con keys (usualmente en columna A).
2. **Validación**:
   - El handler puede revisar que el archivo:
     - Existe y tiene la estructura mínima esperada.
3. **Ejecución del script**:
   - Comando:
     - `scripts.buscar_keys` con:
       - Ruta del Excel.
       - Empresa.
4. **Procesamiento interno (`scripts/buscar_keys.py`)**:
   - Lee la columna de keys.
   - Aplica la misma lógica de búsqueda que el modo manual, pero en lote.
   - Genera el mismo tipo de reporte consolidado:
     - `out/Find_key/Find_Key.xlsx` (puede sobrescribir el anterior).
5. **Salida**:
   - El handler:
     - Informa de la finalización.
     - Muestra el mismo diálogo de éxito con la ruta a `Find_Key.xlsx`.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/importar_all.py`
  - `scripts/Convertir_all.py`
  - `scripts/buscar_key.py`
  - `scripts/buscar_keys.py`
- Configuración:
  - `config/buscar_key.json`:
    - Define qué fuentes/tablas se revisan y cómo se presentan las salidas.
  - `config/db_names.json`:
    - Nombres de bases/tablas para SCADA/HSH/ODS relevantes.

---

## Salidas generadas

- Carpeta:
  - `out/Find_key/`
- Archivo principal:
  - `Find_Key.xlsx`:
    - Hoja(s) con resultados por key.
    - Campos típicos:
      - Key.
      - Fuente (SCADA/HSH/ODS).
      - Tabla/base.
      - Campos adicionales según configuración.

---

## Errores comunes y recomendaciones

- **No hay datos locales suficientes**:
  - Mensaje indicando que faltan SCADA/HSH/ODSTXT.
  - Ejecutar el pipeline de “Actualizar datos” o activar “Actualizar BD”.
- **Keys inválidas en modo manual**:
  - Verificar el formato (8 caracteres, `#####.##` o comodines `%`).
- **Excel de entrada mal estructurado (modo archivo)**:
  - Asegurarse de que la columna de keys esté en el lugar esperado y sin filas vacías inesperadas.
- **Reporte no se genera**:
  - Revisar la consola embebida y `log/buscar_key.log` o `log/buscar_keys.log` para detalles.

Cuando se presenten problemas recurrentes, revisar también si hubo cambios recientes en `config/buscar_key.json` o en la estructura de los CSV de origen.

