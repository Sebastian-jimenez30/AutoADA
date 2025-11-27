# 04-05 – Jobs: Creación de señales SCADA

Este pipeline automatiza la creación de **señales SCADA** (Jobs) a partir de un archivo Excel, generando archivos de carga listos para ser aplicados en el sistema SCADA.

---

## Objetivo del flujo

- Validar la información de nuevas señales propuesta en un Excel.
- Verificar consistencia con datos SCADA actuales.
- Generar archivos de carga y reportes que:
  - Se puedan aplicar en SCADA.
  - Documenten qué se va a crear (y cómo).

---

## Punto de entrada en la UI

- Vista: **Jobs** (`interfaces/marco_jobs.py`).
- Sección: **Crear señales**.
- Elementos:
  - Combo de empresa.
  - Checkbox “Actualizar BD”.
  - Botón “Seleccionar archivo” para el Excel de entrada.
  - Botón “Crear señales” (o similar).
  - Consola embebida.

---

## Entradas necesarias

### Datos locales

- CSV SCADA actualizados para la empresa:
  - `out/<EMPRESA>/SCADA`.

Si no existen o están desactualizados, se recomienda marcar “Actualizar BD”.

### Archivo Excel

- Archivo con la definición de las señales a crear:
  - Basado en la plantilla `ScadaLoad.xlsx` u otra definida en `templates/`.
  - Contiene:
    - Identificadores de señales.
    - Información de configuración necesaria (estación, tipo, descripciones, etc.).

---

## Pasos del pipeline

Handler principal: `handlers/jobs/crear.py` (función equivalente a `ejecutar_crear_senales` descrita en la documentación).

1. **Selección y validación de archivo**
   - El usuario selecciona el Excel de entrada.
   - El handler:
     - Verifica que el archivo existe.
     - Puede revisar columnas mínimas necesarias.
     - Habilita/deshabilita el botón de crear según la selección.

2. **Actualización de BD (opcional)**

Cuando “Actualizar BD” está activo:

- **Importación**:
  - Comando:
    - `scripts.importar_all servidor empresa "sca" --usecase jobs_crear_senales`.
- **Conversión**:
  - Comando:
    - `scripts.Convertir_all empresa "jobs"`.
- **Validación previa**:
  - Se asegura que haya datos SCADA suficientes para los Jobs.

3. **Validación de datos de entrada (`scan_data`)**

- Antes de generar cargas, el pipeline llama a:
  - `scripts.scan_data` con parámetros adecuados.
- Si `scan_data` devuelve código de retorno:
  - `0`: validación OK.
  - `2`: se detectan errores de validación:
    - Se crea un archivo de errores (por ejemplo, `out/validacion_errores.txt`).
    - El handler puede mostrar un resumen y un detalle.

4. **Generación de archivos de carga (`SCADA_S-A`)**

- Comando principal:
  - `scripts.SCADA_S-A` con los parámetros necesarios.
- Procesamiento interno:
  - Usa:
    - Datos SCADA convertidos de `out/<EMPRESA>/SCADA`.
    - El Excel validado de entrada.
  - Genera:
    - Cargas para tablas SCADA.
    - Archivos de resumen.

5. **Salida**

- Archivos generados típicos:
  - `out/Load/10_SCADA.csv`
  - `out/Load/32_FEP.csv`
  - `out/Load/Senales_with_keys.xlsx`
- El handler:
  - Muestra un diálogo de éxito que lista estos archivos.
  - Ofrece abrirlos, mostrar folder, copiar rutas.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/importar_all.py`
  - `scripts/Convertir_all.py`
  - `scripts/scan_data.py`
  - `scripts/SCADA_S-A.py`
- Configuración:
  - `config/import_profiles.json` (perfil `jobs_crear_senales`).
  - `config/scada.json` y otros relacionados a Jobs.
  - Plantilla `templates/ScadaLoad.xlsx`.

---

## Salidas generadas

- Carpeta:
  - `out/Load/`
- Archivos:
  - CSV de carga (ej. `10_SCADA.csv`, `32_FEP.csv`).
  - Excel de resumen (`Senales_with_keys.xlsx` u otros).

Estos archivos son la base para ejecutar Jobs en SCADA y para documentación interna del cambio.

---

## Errores comunes y recomendaciones

- **Validación de `scan_data` fallida**:
  - Revisar `out/validacion_errores.txt` (u otro archivo de detalle).
  - Corregir el Excel de entrada (campos faltantes, tipos incorrectos, valores fuera de rango).
- **Datos SCADA desactualizados**:
  - Volver a ejecutar “Actualizar datos” o marcar “Actualizar BD” en la vista Jobs.
- **Archivos de carga no generados**:
  - Revisar la consola embebida y logs (por ejemplo, `log/Scada_load.log` si existe).
  - Confirmar que no hubo errores silenciosos en scripts intermedios.

Se recomienda versionar o respaldar los archivos de salida críticos antes de aplicar cambios en SCADA.

