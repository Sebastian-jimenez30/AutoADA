# 04-07 – Unifilares: Importar y validar

Este pipeline permite **importar y convertir** datos necesarios para unifilares (SCADA y ODS/ODSTXT) y luego ejecutar la **validación de unifilares** a partir de archivos TXT seleccionados.

---

## Objetivo del flujo

- Validar la consistencia de unifilares comparando:
  - Datos de unifilares (archivos TXT de entrada).
  - Datos SCADA y ODS/ODSTXT importados desde sistemas externos.
- Generar reportes con hallazgos para revisión y corrección.

---

## Punto de entrada en la UI

- Vista: **Unifilares** (`interfaces/marco_unifilares.py`).
- Elementos principales:
  - Selección de empresa y dominio.
  - Checkbox “Actualizar BD”.
  - Botón “Importar/Convertir” (según diseño de la vista).
  - Botón “Seleccionar archivos” para unifilares (TXT).
  - Botón “Ejecutar validaciones”.
  - Consola embebida.

---

## Entradas necesarias

### Datos locales

- SCADA y ODS/ODSTXT convertidos:
  - `out/<EMPRESA>/SCADA`.
  - `out/<EMPRESA>/ODSTXT` (TXT/CSV).

### Parámetros de UI

- **Empresa**:
  - Obligatoria.
- **Dominio**:
  - Usado para resolver servidores y perfiles de importación.
- **Actualizar BD**:
  - Si se marca, se ejecutan importación y conversión antes de permitir la validación.
- **Archivos de unifilares**:
  - Uno o varios archivos TXT seleccionados mediante el selector.

---

## Pipeline – Importar y convertir unifilares

Handler principal: `handlers/unifilares/importar.py` (`importar_y_convertir_unifilares` en la documentación).

1. **Validaciones iniciales**
   - Verificar selección de empresa y dominio.
   - Ajustar botones:
     - Cuando “Actualizar BD” está activo:
       - Deshabilitar botones de selección/ejecución de archivos hasta que termine la importación.

2. **Importación**
   - Ejecución paralela de importaciones (según documentación):
     - `scripts.importar_all servidor empresa "sca" --usecase validar_unifilares`.
     - `scripts.importar_all servidor empresa "ods" --usecase validar_unifilares`.
   - Consola:
     - Prefijos `[IMPORT-SCADA]`, `[IMPORT-ODS]` u otros según implementación.

3. **Conversión**
   - Una vez finalizan las importaciones:
     - Se ejecuta:
       - `scripts.Convertir_all empresa "unifilares" --only ods,ods_csv`.
   - Esto genera:
     - Archivos ODS/ODSTXT convertidos bajo `out/<EMPRESA>/ODSTXT`.

4. **Actualización de UI**
   - Rehabilitar botones de selección y ejecución.
   - Actualizar etiquetas de “última actualización” usando `utils.last_update`.

---

## Pipeline – Validar unifilares

Handler principal: `handlers/unifilares/validar.py` (`ejecutar_validaciones_unifilares` en la documentación).

1. **Selección de archivos**
   - El usuario selecciona uno o varios archivos TXT de unifilares.
   - El helper `mostrar_boton_seleccionar_archivo_unifilares` coordina:
     - Estado de botones según empresa/dominio/checkbox/archivos seleccionados.

2. **Ejecución de validación**
   - Comando principal:
     - `scripts.Validacion_unifilares` con:
       - Empresa.
       - Lista de archivos TXT seleccionados.
   - `TaskRunner` lanza el subproceso:
     - La consola muestra mensajes con prefijos de etapa.

3. **Procesamiento interno (`scripts/Validacion_unifilares.py`)**
   - Lee:
     - Archivos TXT de unifilares.
     - Datos SCADA.
     - Datos ODS/ODSTXT convertidos.
   - Aplica reglas de validación específicas de unifilares:
     - Coherencia de tags.
     - Correspondencia entre unifilares y señales SCADA.
   - Genera reportes bajo:
     - `out/Validacion_Unifilares/` (ruta típica).

4. **Salida**
   - El handler:
     - Captura rutas de archivos relevantes (si las imprime el script).
     - Muestra un diálogo de éxito listando los reportes generados.
     - Deja trazas en consola para diagnóstico.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/importar_all.py`
  - `scripts/Convertir_all.py`
  - `scripts/Validacion_unifilares.py`
  - `scripts/Leer_unifilares.py` (apoyo en lectura de unifilares).
- Configuración:
  - `config/import_profiles.json` (uso de `validar_unifilares`).
  - Otros archivos `config/*.json` para mapeos de tablas/campos usados en la validación.

---

## Salidas generadas

- Carpeta:
  - `out/Validacion_Unifilares/`
- Archivos:
  - Uno o varios Excel/CSV con:
    - Hallazgos específicos por unifilar.
    - Resúmenes de inconsistencias.

El nombre exacto de los archivos depende de la implementación del script, pero el handler se encarga de listarlos en el diálogo de éxito.

---

## Errores comunes y recomendaciones

- **Dominio/empresa no seleccionados**:
  - La UI debe impedir lanzar el pipeline hasta completar estos campos.
- **Archivos TXT no seleccionados**:
  - El handler muestra un mensaje claro pidiendo seleccionar uno o más archivos.
- **Datos SCADA/ODSTXT desactualizados**:
  - Ejecutar antes el pipeline de importación/conversión con “Actualizar BD”.
- **Reportes vacíos o incompletos**:
  - Verificar si las reglas de validación corresponden a la versión actual de los datos y plantillas de unifilares.

Como siempre, revisar la consola embebida y logs generados es clave para entender qué ocurrió en cada etapa.

