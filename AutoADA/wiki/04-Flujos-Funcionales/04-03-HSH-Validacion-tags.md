# 04-03 – HSH: Validación de tags

Este pipeline valida la coherencia de **tags HSH** comparando información entre HSH, SCADA y otras fuentes, generando reportes de inconsistencias y hallazgos.

---

## Objetivo del flujo

- Detectar problemas en tags HSH, tales como:
  - Tags faltantes en alguna de las bases.
  - Inconsistencias de nombres, tipos o configuraciones.
  - Diferencias entre empresa principal y de respaldo (cuando aplica).
- Producir reportes claros para inspección y corrección posterior.

---

## Punto de entrada en la UI

- Vista: **HSH** (`interfaces/marco_hsh.py`).
- Sección: **Validar** (dentro de la pestaña o panel HSH).
- Elementos:
  - Selección de **empresa** (y eventualmente empresa de respaldo).
  - Opciones de **actualizar BD** (SCADA/HSH).
  - Etiquetas que muestran:
    - Última actualización SCADA/HSH.
    - Estado de datos para empresa principal y respaldo.
  - Botón para lanzar **Validación HSH**.
  - Consola embebida.

---

## Entradas necesarias

### Datos locales

- CSV convertidos en:
  - `out/<EMPRESA>/SCADA`.
  - `out/<EMPRESA>/HSH`:
    - `groups.csv`.
    - `lookup_table.csv`.
- Opcionalmente, datos para empresa **respaldo** (por ejemplo, ITCO↔TRA, REPS↔REPP).

### Parámetros de UI

- **Empresa principal**:
  - Selección obligatoria.
- **Empresa respaldo** (si aplica):
  - Opcional; cuando se usa, se generan comparaciones cruzadas.
- **Actualizar BD**:
  - Si está activo, antes de validar:
    - Se importan y convierten datos SCADA/HSH para empresa principal (y respaldo).

---

## Pasos del pipeline

Handler principal: `handlers/hsh/validar.py` (función equivalente a `ejecutar_validacion_hsh` descrita en la documentación).

1. **Validaciones iniciales**
   - Verificar que:
     - Se ha seleccionado una empresa válida.
     - Opcionalmente, que la empresa respaldo es compatible.
   - Mostrar mensajes claros si falta información.

2. **Actualización de datos (opcional)**
   - Si “Actualizar BD” está activo:
     - Para empresa principal (y respaldo, si corresponde):
       - Comando de importación:
         - `scripts.importar_all servidor empresa "sca,hsh" --usecase hsh_validar --flex`.
       - Comando de conversión:
         - `scripts.Convertir_all empresa "Validar_HSH" --only sca`.
         - `scripts.Convertir_all empresa "Validar_HSH" --only hsh`.
     - Se actualizan etiquetas de última carga SCADA/HSH.

3. **Ejecución de la validación**
   - Se construye comando:
     - `scripts.validaciones_hsh` con:
       - Empresa principal.
       - Parámetros adicionales según configuración (por ejemplo, empresa respaldo).
   - `TaskRunner` lanza el subproceso:
     - Prefijos de etapa en consola (por ejemplo, `[VALIDACION HSH]`).
     - Captura errores y progreso.

4. **Procesamiento interno (`scripts/validaciones_hsh.py`)**
   - Lee:
     - CSV SCADA de `out/<EMPRESA>/SCADA`.
     - CSV HSH (`groups.csv`, `lookup_table.csv`) de `out/<EMPRESA>/HSH`.
     - Datos de respaldo, si aplica.
   - Aplica reglas de validación configuradas (según `config/`):
     - Comparación de estructuras, nombres, tipos, etc.
   - Genera uno o varios reportes:
     - Bajo `out/Validaciones_<EMPRESA>/`.

5. **Salida**
   - El handler:
     - Rehabilita botones.
     - Llama a un diálogo de éxito que:
       - Lista todos los archivos de validación encontrados en `out/Validaciones_<EMPRESA>/`.
       - Ofrece opciones para:
         - Abrirlos.
         - Mostrar la carpeta.
         - Copiar rutas.
     - Actualiza etiquetas de estado en la UI si corresponde.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/importar_all.py`
  - `scripts/Convertir_all.py`
  - `scripts/validaciones_hsh.py`
  - `scripts/import_scada.py`, `scripts/import_hsh.py` (dependencias de `importar_all`).
- Configuración:
  - `config/import_profiles.json`:
    - Define perfiles de importación para `hsh_validar`.
  - Otros archivos en `config/` relacionados con SCADA/HSH.

---

## Salidas generadas

- Carpeta:
  - `out/Validaciones_<EMPRESA>/`
- Archivos típicos:
  - Diferentes reportes Excel, por ejemplo:
    - Listados de tags inconsistentes.
    - Resúmenes de diferencias entre SCADA y HSH.
    - Reportes por empresa principal y respaldo.

El número y nombre exacto de los archivos puede variar según la configuración y la evolución de los scripts.

---

## Errores comunes y recomendaciones

- **Datos incompletos en HSH/SCADA**:
  - Mensajes en la consola indicando archivos faltantes.
  - Verificar que:
    - Se ejecutó el pipeline de actualización de datos.
    - Se importaron correctamente SCADA y HSH para la empresa.
- **Errores de conexión a Mongo**:
  - Revisar variables de entorno (MONGO_USER/PASS/HOSTS).
  - Ejecutar `scripts/test_mongo.py` para diagnóstico.
- **Reportes vacíos o con pocas entradas**:
  - Confirmar que las reglas de validación coincidan con lo esperado (posibles cambios en la estructura de datos).
  - Revisar si hubo cambios recientes en `config/` o en la estructura de CSV de origen.

En caso de dudas, revisar la consola embebida y los logs asociados (por ejemplo, `log/validaciones_hsh.log` si existe, o el log general de importaciones).

