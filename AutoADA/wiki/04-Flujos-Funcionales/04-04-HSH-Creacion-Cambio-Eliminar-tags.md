# 04-04 – HSH: Creación, cambio y eliminación de tags

Este conjunto de pipelines permite **crear**, **cambiar key** y **eliminar** tags en HSH de forma controlada, a partir de archivos Excel y datos locales actualizados.

---

## Objetivo de los flujos

- Reducir errores manuales en la administración de tags HSH.
- Asegurar que las operaciones sigan reglas de negocio definidas.
- Producir reportes claros sobre qué cambios se realizaron o propondrán.

---

## Punto de entrada en la UI

- Vista: **HSH** (`interfaces/marco_hsh.py`).
- Secciones:
  - **Crear Tag HSH**.
  - **Cambiar Key HSH**.
  - **Eliminar Tag HSH**.
- Elementos comunes:
  - Selección de empresa (y backup, si aplica).
  - Checkbox “Actualizar BD” (para refrescar SCADA/HSH).
  - Selección de archivo Excel con tags a procesar.
  - Consola embebida.

---

## Entradas necesarias

### Datos locales

- SCADA/HSH actualizados para la empresa (y respaldo, cuando corresponda):
  - `out/<EMPRESA>/SCADA`.
  - `out/<EMPRESA>/HSH`.

En muchos casos, la UI puede forzar “Actualizar BD” si no encuentra datos suficientes.

### Archivos Excel

Para cada flujo:

- **Crear Tag HSH**:
  - Excel con columnas requeridas según `HSH_TEMPLATE.xlsx`.
- **Cambiar Key HSH**:
  - Excel que indica mapeos de keys antiguas/nuevas, con columnas obligatorias definidas en plantilla correspondiente.
- **Eliminar Tag HSH**:
  - Excel con tags a eliminar y campos mínimos de identificación.

La validación de estructura (columnas obligatorias) se realiza en los scripts y/o handlers.

---

## Pipeline – Crear Tag HSH

Handler principal: `handlers/hsh/crear.py` (función equivalente a `ejecutar_crear_tag_hsh` en la documentación).

1. **Selección y validación de archivo**
   - El usuario selecciona un Excel basado en `HSH_TEMPLATE.xlsx`.
   - El handler:
     - Verifica que el archivo existe.
     - Puede validar columnas mínimas requeridas.

2. **Actualización de BD (opcional)**
   - Si “Actualizar BD” está activo:
     - Importa SCADA y HSH para empresa principal (y respaldo, si aplica):
       - `scripts.importar_all servidor empresa "sca,hsh" --usecase hsh_crear_tag`.
     - Ejecuta conversiones granulares:
       - `scripts.Convertir_all empresa "Validar_HSH" --only sca`.
       - `scripts.Convertir_all empresa "Validar_HSH" --only hsh`.
   - Actualiza etiquetas de última carga SCADA+HSH.

3. **Ejecución de creación de tags**
   - Se construye comando:
     - `scripts.hsh_crear_tag --input <excel>` y otros parámetros:
       - `--server <hostname>` para apuntar al entorno correcto (derivado de `ServerResolver`).
       - `--apply` (si el usuario confirma la aplicación real en HSH).
   - `TaskRunner` lanza el subproceso:
     - Consola muestra progreso ([VALIDACION], [CREACION], etc.).

4. **Procesamiento interno (`scripts/hsh_crear_tag.py`)**
   - Valida el contenido del Excel.
   - Realiza comprobaciones previas usando datos SCADA/HSH convertidos.
   - Si se pasa `--apply`:
     - Inserta los tags en HSH.
   - Genera:
     - Rutas de reportes (`REPORT_PATH`, `INFO_PATH`, `QUERY_PATH`) en stdout.

5. **Salida**
   - El handler:
     - Interpreta las líneas con `REPORT_PATH`, `INFO_PATH`, `QUERY_PATH`.
     - Construye un diálogo de éxito, listando los archivos relevantes.
     - Actualiza etiquetas de última carga SCADA+HSH.

---

## Pipeline – Cambiar Key HSH

Aunque los detalles exactos dependen de la implementación actual de `handlers/hsh/cambiar_key.py` y `scripts/hsh_cambiar_key.py`, el flujo típico es:

1. **Selección de archivo**
   - Excel con columnas que identifican:
     - Tag actual.
     - Nueva key.
     - Información adicional necesaria.

2. **Actualización de BD (opcional)**
   - Similar al flujo de creación:
     - Importar y convertir SCADA/HSH según sea necesario.

3. **Ejecución de cambio de key**
   - Comando:
     - `scripts.hsh_cambiar_key --input <excel> [--apply] --server <hostname> ...`.
   - La consola muestra validaciones y cambios propuestos/aplicados.

4. **Reportes**
   - Se generan archivos que documentan:
     - Qué keys se intentó cambiar.
     - Cuáles fueron aceptadas, rechazadas o requieren revisión.
   - El handler muestra un diálogo con la lista de archivos resultantes.

---

## Pipeline – Eliminar Tag HSH

Flujo habitual apoyado en `handlers/hsh/eliminar.py` y `scripts/hsh_eliminar_tag.py`:

1. **Selección de archivo**
   - Excel con tags a eliminar.

2. **Actualización de BD (opcional)**
   - Importar/convertir SCADA/HSH si no hay datos recientes.

3. **Ejecución de eliminación**
   - Comando:
     - `scripts.hsh_eliminar_tag --input <excel> [--apply] --server <hostname> ...`.
   - Se valida que los tags existan y cumplan criterios para eliminación.

4. **Reportes**
   - Resultados en uno o más Excel:
     - Tags eliminados.
     - Tags que no pudieron eliminarse y motivos.
   - El handler muestra diálogo con archivos generados.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/importar_all.py`, `scripts/Convertir_all.py`.
  - `scripts/hsh_crear_tag.py`.
  - `scripts/hsh_cambiar_key.py`.
  - `scripts/hsh_eliminar_tag.py`.
  - Otros utilitarios de importación/conversión usados por estos scripts.
- Configuración:
  - `config/import_profiles.json` (perfiles `hsh_crear_tag`, `hsh_validar`, etc.).
  - `config/diccionario_tags.json` y otros JSON relacionados a HSH.
  - Plantilla `templates/HSH_TEMPLATE.xlsx` como referencia de estructura.

---

## Salidas generadas

Dependiendo del flujo y la implementación, típicamente se generan:

- Archivos de reportes en `out/Validaciones_<EMPRESA>/` o en otras rutas específicas para HSH.
- Logs específicos para HSH en `log/` (por ejemplo, `hsh_crear_tag.log`, si se implementa).
- Archivos auxiliares que resumen:
  - Cambios aplicados.
  - Cambios propuestos.
  - Errores detectados.

Los handlers se encargan de presentar estos archivos de manera amigable mediante diálogos de éxito con accesos directos.

---

## Errores comunes y recomendaciones

- **Estructura de Excel incorrecta**:
  - Verificar que los archivos sigan exactamente las plantillas esperadas.
  - Revisar mensajes de error de los scripts (`columnas faltantes`, `tipos inválidos`, etc.).
- **Errores de conexión a HSH/Mongo**:
  - Confirmar credenciales y endpoints en el vault.
  - Ejecutar scripts de prueba (por ejemplo, `test_mongo`) si hay dudas.
- **Cambios no aplicados**:
  - Revisar si se ejecutó el pipeline en modo “dry-run” (sin `--apply`).
  - Consultar reportes generados para entender por qué algunos tags no se modificaron.

Siempre que se vayan a aplicar cambios en HSH (especialmente en entornos productivos), se recomienda:

- Revisar cuidadosamente los reportes previos.
- Realizar pruebas en entornos controlados cuando sea posible.

