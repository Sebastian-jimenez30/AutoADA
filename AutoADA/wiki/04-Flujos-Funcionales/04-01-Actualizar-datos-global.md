# 04-01 – Actualizar datos global (perfil default)

Este pipeline sincroniza los datos locales de **SCADA**, **HSH** y **ODS** para todas las empresas permitidas en el entorno actual, usando el perfil de importación “default”.

---

## Objetivo del flujo

- Descargar desde servidores remotos los dumps SCADA/HSH/ODS necesarios.
- Convertir estos dumps a formatos de trabajo (CSV/TXT) organizados por empresa.
- Dejar preparados los datos para que otros módulos (Buscar Keys, HSH, Jobs, Unifilares, PyP, RTU) trabajen sobre información actualizada.

Es la base sobre la que dependen muchos otros pipelines.

---

## Punto de entrada en la UI

- Vista: **Bienvenida / Estado de datos** (`interfaces/marco_bienvenida.py`).
- Botón principal:
  - `Actualizar datos` (ejecuta el perfil default).
- Botón secundario:
  - `Refrescar estado` (solo recalcula la última actualización; no ejecuta el pipeline).

---

## Entradas necesarias

- **Empresas permitidas**:
  - Derivadas de `SecurityService.empresas_permitidas(ubicacion)` según el hostname.
  - Ejemplos:
    - ITCO: `["ITCO", "TRA"]`.
    - REP: `["REPS", "REPP"]`.
- **Servidores remotos**:
  - Resueltos mediante `ServerResolver.generar_server(empresa, dominio="CC")`.
  - Configurados en `config/servers.json`.
- **Credenciales y parámetros**:
  - Provistos por el vault:
    - Usuario y contraseña Mongo.
    - Usuario, llave y puerto SSH.
    - Parámetros ODBC/HIS si aplica.
  - Inyectados en el entorno de ejecución (`secure_env()`).

Si no se puede resolver servidor para una empresa o faltan datos de entorno, esa empresa se reporta como error.

---

## Pasos del pipeline

Implementación principal: `handlers/actualizar_datos.py::ejecutar_actualizar_datos_default(app)`.

1. **Determinación de empresas objetivo**
   - Obtiene empresas permitidas desde `AppController`.
   - Normaliza y filtra valores vacíos o marcadores (“Empresa...”).

2. **Resolución de servidores**
   - Para cada empresa:
     - Intenta `generar_server(empresa, "CC")`.
     - Si falla, añade un mensaje de error para esa empresa.
   - Si ninguna empresa tiene servidor válido:
     - Muestra un error y termina el pipeline.

3. **Preparación de la UI**
   - Deshabilita el botón `Actualizar datos` y cambia el texto a “Actualizando...”.
   - Limpia la consola, si existe.
   - Inicia la barra de estado en modo indeterminado (“Sincronizando datos (perfil default)...”).

4. **Importación por empresa**
   - Para cada `(empresa, servidor)` en la cola:
     - Construye comando:
       - `scripts.importar_all servidor empresa "sca,hsh,ods"`.
     - Escribe en la consola:
       - Línea `[IMPORT:EMPRESA]` con el comando ejecutado.
     - Ejecuta el subproceso con `TaskRunner`:
       - Envía `on_progress` para etiquetar líneas con prefijo `[IMPORT-EMPRESA]`.
       - Captura errores y los agrega a la lista `errors` si el returncode != 0.

5. **Conversión por componentes**
   - Si la importación de una empresa finaliza con éxito:
     - Se ejecutan, en secuencia, conversiones granulares para componentes:
       - `sca`, `hsh`, `ods`, `ods_csv`.
     - Para cada componente:
       - Comando: `scripts.Convertir_all empresa "Buscar_keys" --only <componente>`.
       - Prefijo de consola: `[CONVERT-EMPRESA-COMPONENTE]`.
       - Si una conversión falla, se registra como error, se continúa con la siguiente empresa.
   - Si todas las conversiones de una empresa tienen éxito:
     - La empresa se añade a la lista `completed`.

6. **Finalización y resumen**
   - Una vez terminan todas las empresas:
     - Reactiva el botón `Actualizar datos` con el texto original.
     - Detiene la barra de estado.
     - Llama a `refresh_estado_datos()` (si existe) para recalcular últimas actualizaciones en la vista de bienvenida.
   - Mensajes finales:
     - Si todas fallan → error general.
     - Si algunas completan y otras fallan → advertencia.
     - Si todas completan → éxito con listado de empresas actualizadas.
   - En caso de éxito o éxito parcial:
     - Se muestra un diálogo de éxito/resumen, apuntando al log `out/log/importar.log` si está disponible.

---

## Scripts involucrados

- `scripts/importar_all.py`:
  - Descarga datos SCADA, HSH y ODS para cada empresa.
  - Escribe logs en `log/importar.log`.
- `scripts/import_scada.py`, `scripts/import_hsh.py`, `scripts/import_ods.py`:
  - Implementan la lógica específica de cada tipo de importación.
- `scripts/Convertir_all.py`:
  - Convierte los dumps en CSV/TXT para SCADA/HSH/ODS/ODSTXT.

---

## Salidas generadas

Por empresa (`<EMPRESA>`):

- En AppData:
  - `db/<EMPRESA>/` con dumps importados (staging).
- En la carpeta de ejecución:
  - `out/<EMPRESA>/SCADA`:
    - CSV SCADA (por ejemplo, `10_*.csv`, `32_*.csv`).
  - `out/<EMPRESA>/HSH`:
    - CSV para HSH (por ejemplo, `groups.csv`, `lookup_table.csv`).
  - `out/<EMPRESA>/ODSTXT`:
    - TXT/CSV de ODS convertidos.
- Logs:
  - `log/importar.log` con detalle de todas las importaciones.

Estos datos son reutilizados por otros módulos sin necesidad de reimportar mientras sigan vigentes.

---

## Indicadores visuales en la UI

- Pantalla de bienvenida:
  - Muestra, por dataset (SCADA, HSH, ODSTXT), la última actualización detectada:
    - Fecha/hora.
    - Hace cuánto tiempo.
    - Empresa para la cual se detectó la actualización más reciente.
- Consola:
  - Detalla comandos ejecutados y mensajes de importación/conversión.
  - Marca errores y advertencias con diferentes colores.
- Barra de estado:
  - Indica el progreso general (“Importando datos para <EMPRESA>...”, “Convirtiendo...”, etc.).

---

## Errores comunes y cómo actuar

- **No se pudo resolver servidor para ninguna empresa**:
  - Verificar `config/servers.json`.
  - Confirmar que `SecurityService` está identificando correctamente la ubicación (hostname).
- **Errores recurrentes en importar_all**:
  - Revisar conectividad a servidores SCADA/HSH/ODS.
  - Revisar credenciales y rutas configuradas en el vault.
  - Consultar `log/importar.log` para detalles.
- **Errores en conversión (`Convertir_all`)**:
  - Verificar que los dumps importados tienen el formato esperado.
  - Revisar versiones de pandas/numpy si hay errores de lectura de CSV/TXT.

Si el problema persiste, se recomienda ejecutar los scripts manualmente (modo desarrollo) y revisar la salida directa de consola para diagnóstico avanzado.

