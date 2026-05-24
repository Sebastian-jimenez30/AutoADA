# 04-06 – Jobs: Eliminar y cambiar nombre de señales SCADA

Este conjunto de pipelines permite **eliminar** y **cambiar nombre** de señales SCADA, generando archivos de carga/descarga que pueden aplicarse en el sistema SCADA.

---

## Objetivo de los flujos

- Facilitar cambios masivos en señales ya existentes:
  - Eliminación de señales obsoletas.
  - Actualización de nombres siguiendo nuevas convenciones.
- Asegurar que estos cambios se ejecuten:
  - Sobre datos SCADA actualizados.
  - Con validaciones previas para minimizar errores.

---

## Punto de entrada en la UI

- Vista: **Jobs** (`interfaces/marco_jobs.py`).
- Secciones:
  - **Eliminar señales**.
  - **Cambiar nombre de señales**.
- Elementos en cada sección:
  - Combo de empresa.
  - Checkbox “Actualizar BD”.
  - Botón “Seleccionar archivo” para el Excel de entrada.
  - Botón “Eliminar” o “Cambiar nombre”.
  - Consola embebida.

---

## Entradas necesarias

### Datos locales

- CSV SCADA actualizados para la empresa:
  - `out/<EMPRESA>/SCADA`.

Se recomienda marcar “Actualizar BD” si no se ha corrido recientemente el pipeline de actualización.

### Archivos Excel

- **Eliminar señales**:
  - Excel con señales a eliminar:
    - Identificadores de señal.
    - Estación, tipo y otros campos requeridos según la plantilla configurada.
- **Cambiar nombre**:
  - Excel con información de:
    - Señal actual.
    - Nuevo nombre.
    - Otros campos que se necesiten para validar y aplicar el cambio.

---

## Pipeline – Eliminar señales

Handler principal: `handlers/jobs/eliminar.py` (`ejecutar_eliminar_senales` en la documentación).

1. **Selección y validación de archivo**
   - El usuario selecciona Excel de eliminación.
   - El handler:
     - Verifica existencia.
     - Habilita/deshabilita botón según estado.

2. **Actualización de BD (opcional)**

Cuando “Actualizar BD” está activo:

- **Importación**:
  - Comando (similar a creación de señales, pero con usecase específico si aplica):
    - `scripts.importar_all servidor empresa "sca" --usecase jobs_eliminar_senales` (nombre aproximado, según perfil).
- **Conversión**:
  - `scripts.Convertir_all empresa "jobs"`.

3. **Validación (scan_data)**

- Al igual que en creación de señales:
  - Se ejecuta `scripts.scan_data` para validar el Excel de entrada.
  - Código de retorno:
    - `0`: OK.
    - `2`: errores de validación → archivo de errores (por ejemplo, `out/validacion_errores.txt`).

4. **Generación de archivos de eliminación**

- Comando principal:
  - `scripts.eliminar_senales_scada` (o variante) con parámetros adecuados.
- Procesamiento interno:
  - Usa CSV SCADA convertidos.
  - Aplica lógica para:
    - Determinar qué filas/tablas deben modificarse.
    - Generar scripts/CSV de eliminación.

5. **Salida**

- Carpeta:
  - `out/Delete/`
- Archivos típicos:
  - `Delete_scada.csv`
  - `change_key.csv`
  - `Delete_controls.csv`
- El handler:
  - Muestra un diálogo de éxito con la lista de archivos.

---

## Pipeline – Cambiar nombre de señales

Handler principal: `handlers/jobs/cambiar_nombre.py` (`ejecutar_cambiar_nombre_senales` en la documentación).

1. **Selección y validación de archivo**
   - Excel con mapeos de nombres:
     - Señal actual.
     - Nuevo nombre.
   - Verificación de existencia y estructura básica.

2. **Actualización de BD (opcional)**

Cuando “Actualizar BD” está activo:

- Similar a eliminación:
  - Importación SCADA para la empresa.
  - Conversión mediante `Convertir_all` en modo `jobs`.

3. **Validación de datos (scan_data)**

- Se puede reutilizar `scan_data` para asegurar que:
  - Las señales existan en datos SCADA.
  - Los nuevos nombres cumplan reglas de formato.

4. **Generación de archivos de cambio de nombre**

- Comando principal:
  - `scripts.cambiar_nombre_senales_scada` (o script equivalente).
- Procesamiento:
  - Determina qué filas de tablas deben cambiar.
  - Genera CSV de cambio de key/nombre (por ejemplo, `change_key.csv`).

5. **Salida**

- Carpeta:
  - `out/Name/` (según implementación).
- Archivos:
  - `change_key.csv` y otros que se definan.
- El handler:
  - Muestra un diálogo de éxito con rutas a los archivos generados.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/importar_all.py`
  - `scripts/Convertir_all.py`
  - `scripts/scan_data.py`
  - `scripts/eliminar_senales_scada.py`
  - `scripts/cambiar_nombre_senales_scada.py`
  - Posiblemente `scripts/Eliminar_y_cambiar_name_senales.py` en flujos más antiguos.
- Configuración:
  - `config/import_profiles.json` (perfiles específicos para Jobs).
  - `config/scada.json` y otros JSON relacionados a SCADA.
  - Plantillas Excel correspondientes a eliminar/cambiar nombre.

---

## Errores comunes y recomendaciones

- **Errores de validación en `scan_data`**:
  - Revisar el archivo de errores generado.
  - Corregir el Excel de entrada (datos faltantes, formatos incorrectos).
- **Datos SCADA desactualizados**:
  - Ejecutar primero “Actualizar datos” o usar la opción “Actualizar BD” en la vista Jobs.
- **Archivos de salida incompletos**:
  - Revisar la consola y logs específicos (por ejemplo, `Scada_load.log`, `eliminar.log` si existen).
  - Confirmar que todos los pasos (importar, convertir, validar) se completaron sin errores.

Siempre se recomienda:

- Probar los archivos generados en entornos de prueba.
- Versionar los reportes de eliminación/cambio de nombre como evidencia de cambios aplicados.

