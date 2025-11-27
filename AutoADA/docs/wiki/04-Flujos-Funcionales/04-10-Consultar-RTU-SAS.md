# 04-10 – Consultar RTU / SAS

Este pipeline permite generar reportes sobre **RTU/SAS** usando datos SCADA ya convertidos, sin necesidad de que el usuario arme consultas complejas manualmente.

---

## Objetivo del flujo

- Obtener información consolidada de RTU/SAS basada en:
  - Tablas SCADA convertidas (`32_*`, `10_*`, etc.).
- Facilitar análisis sobre:
  - Equipos (RTU/SAS) seleccionados.
  - Señales asociadas.
  - Configuraciones relevantes.

---

## Punto de entrada en la UI

- Vista: **Consultar** (`interfaces/marco_consultar.py`).
- Sección: **RTU / SAS**.
- Elementos:
  - Combo de empresa.
  - Lista de RTU/SAS disponibles (Listbox).
  - Botón “Consultar RTU/SAS”.
  - Consola embebida.

La lista de RTU/SAS suele derivarse de datos SCADA (por ejemplo, desde `32_6.csv`).

---

## Entradas necesarias

### Datos locales

- CSV SCADA convertidos para la empresa:
  - `out/<EMPRESA>/SCADA`, incluyendo archivos:
    - `32_10.csv`, `32_20.csv`, `10_2.csv`, `10_4.csv`, `10_5.csv`, `10_7.csv`, etc.

Estos archivos son usados internamente por `scripts/consultar_rtu.py`.

### Parámetros de UI

- **Empresa**:
  - Debe seleccionarse antes de consultar.
- **RTU/SAS**:
  - Uno o varios elementos seleccionados en la lista.

Si faltan empresa o selección de RTU/SAS, el handler muestra mensajes de error y no lanza el pipeline.

---

## Pasos del pipeline

Handler principal: `handlers/consultar/rtu.py::ejecutar_consulta_rtu(app)`.

1. **Validaciones de entrada**
   - Verifica:
     - Que `opcion_empresa_consultar` tenga una empresa válida.
     - Que la lista de RTU/SAS (`rtu_listbox`) tenga opciones cargadas (`rtu_current_options`).
     - Que el usuario haya seleccionado al menos una RTU/SAS.

2. **Preparación de la UI**
   - Deshabilita el botón “Consultar RTU” y cambia el texto a “Consultando...”.
   - Limpia la consola si existe.
   - Inicia la barra de estado (“Consultando RTU/SAS”, indeterminada).

3. **Construcción del comando**
   - Combina las RTU/SAS seleccionadas en una cadena, por ejemplo:
     - `"106: SABANT, 128: SABA_TRN"`.
   - Construye el comando:
     - `scripts.consultar_rtu --empresa <EMPRESA> --rtus "<lista_rtus>"`.
   - Obtiene el entorno seguro con `app.secure_env()` y usa `app.base_dir` como `cwd`.

4. **Ejecución del script**
   - `TaskRunner.run_subprocess` lanza el comando.
   - `on_progress(line)`:
     - Limpia y clasifica la línea.
     - Marca errores si contienen `"error"` (actualiza status a error).
     - Actualiza el estado si contienen mensajes clave (por ejemplo, “consultando”, “archivo generado”).
     - Detecta líneas con prefijo `RTU_REPORT:`:
       - Extrae la ruta del reporte y la guarda en un dict `report_holder`.
     - Escribe todas las líneas en la consola con tags `info`/`error`.

5. **Finalización**
   - `on_done(rc)`:
     - Se ejecuta en el hilo de Tk mediante `ventana.after`.
     - Restaura el texto y estado del botón.
     - Detiene la barra de estado.
     - Si `rc == 0`:
       - Llama a `success_status("Consulta RTU lista")`.
       - Verifica la ruta en `report_holder["path"]`:
         - Si es relativa, la combina con `app.base_dir`.
         - Si el archivo existe, muestra un diálogo de éxito (`show_success_with_open`) apuntando a ese archivo.
         - Si no, muestra un mensaje informativo indicando que se consulte la consola.
     - Si `rc != 0`:
       - Llama a `error_status("Consulta RTU termino con errores")`.
       - Muestra un mensaje de error genérico (“Revisa la consola”).

---

## Procesamiento interno (`scripts/consultar_rtu.py`)

Características principales:

- Usa `pandas` para leer múltiples CSV SCADA en `out/<EMPRESA>/SCADA`.
- Define mapeos y diccionarios internos:
  - Por ejemplo, mapeos de RTU, tipos, formatos de control, etc.
- Paso típico:
  - Lectura de tablas:
    - `32_10.csv`, `32_20.csv`, `10_2.csv`, `10_4.csv`, `10_5.csv`, `10_7.csv`.
  - Creación de diccionarios:
    - Mapeos de keys a `IntParms`, estaciones, nombres, etc.
  - Procesamiento de la lista de RTUs:
    - Divide entradas tipo `"106: SABANT"` en número y nombre.
    - Selecciona filas relevantes de las tablas.
  - Generación de un Excel de reporte:
    - Con información por RTU/SAS y señal.
- Logging:
  - Usa `_Logger` para escribir en `log/consultar_rtu.log`.
  - Emite mensajes informativos en consola y una línea `RTU_REPORT: <ruta>` al generar el archivo final.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/consultar_rtu.py`
  - `scripts/_Logger.py` (logging).
- Datos:
  - CSV SCADA en `out/<EMPRESA>/SCADA`.
- Configuración:
  - `config/scada.json` u otros JSON asociados a mapeos de tablas SCADA (si aplica).

---

## Salidas generadas

- Carpeta:
  - Por defecto, dentro de `out/` (posiblemente `out/pruebas/` o ruta específica, según implementación de `consultar_rtu.py`).
- Archivo principal:
  - Reporte de RTU/SAS (normalmente un Excel) cuya ruta se comunica mediante `RTU_REPORT:` en stdout.

El handler se encarga de presentar este archivo en el diálogo de éxito.

---

## Errores comunes y recomendaciones

- **Sin RTU/SAS disponibles en la lista**:
  - Verificar que los CSV SCADA existan y estén actualizados.
  - Revisar la lógica que carga la lista de RTU/SAS en `marco_consultar.py`.
- **Sin selección en la lista**:
  - La UI muestra un error indicando que se debe seleccionar al menos una RTU o SAS.
- **Errores leyendo CSV**:
  - Revisar la consola y `log/consultar_rtu.log`.
  - Confirmar que las tablas SCADA tienen las columnas esperadas.

Si el pipeline falla sistemáticamente, es útil:

- Ejecutar `scripts/consultar_rtu.py` manualmente desde consola con los mismos argumentos.
- Verificar que la estructura de los CSV no haya cambiado (por ejemplo, por actualizaciones de SCADA).

