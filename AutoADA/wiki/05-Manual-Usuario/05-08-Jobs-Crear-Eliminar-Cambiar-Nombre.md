# 05-08 – Jobs: Crear, eliminar y cambiar nombre de señales

Esta página reúne el uso de los tres flujos principales de **Jobs SCADA**:

- Crear señales.
- Eliminar señales.
- Cambiar nombre de señales.

Todos se manejan desde la vista **Jobs** y comparten patrones similares.

---

## Requisitos comunes

- Plantillas Excel correctas para cada operación:
  - Crear: basada en `ScadaLoad.xlsx` (u otra plantilla acordada).
  - Eliminar: Excel con señales a retirar.
  - Cambiar nombre: Excel con mapeo señal actual → nuevo nombre.
- Datos SCADA actualizados:
  - Se recomienda ejecutar “Actualizar datos” o marcar “Actualizar BD” en la vista Jobs.

---

## Pasos comunes (para los tres flujos)

1. **Abrir la vista Jobs**
   - En el menú lateral, selecciona **Jobs**.
   - Verás secciones separadas para Crear, Eliminar y Cambiar nombre.

2. **Seleccionar empresa**
   - En cada sección, elige la empresa en el combo correspondiente.
   - Algunas empresas pueden no estar disponibles para Jobs según la ubicación.

3. **Actualizar BD (opcional, recomendado)**
   - Marca **Actualizar BD** si no estás seguro del estado de los datos SCADA.
   - AutomatizADA importará y convertirá SCADA en modo `jobs` para la empresa.

4. **Seleccionar archivo Excel**
   - Pulsa **Seleccionar archivo** en la sección que vayas a usar.
   - Elige el Excel adecuado (crear, eliminar o cambiar nombre).
   - El botón se actualizará indicando que el archivo está seleccionado.

5. **Ejecutar la operación**
   - Pulsa el botón correspondiente:
     - **Crear señales**.
     - **Eliminar señales**.
     - **Cambiar nombre**.
   - Mientras corre:
     - El botón se deshabilita y su texto muestra el estado.
     - La consola muestra:
       - Validaciones de archivo (via `scan_data` cuando aplica).
       - Importaciones/conversiones (si se marcó “Actualizar BD”).
       - Etapas de generación de archivos (`[SCADA S-A]`, `[ELIMINAR]`, `[CAMBIO]`, etc.).

6. **Revisar resultados**
   - Al finalizar:
     - Se abrirá un diálogo de resumen indicando los archivos generados.
     - Podrás abrirlos, mostrar su carpeta o copiar rutas.

---

## Crear señales

Resultados típicos:

- Carpeta:
  - `out/Load/`
- Archivos:
  - `10_SCADA.csv` (carga para tabla 10_*).
  - `32_FEP.csv` (carga para tabla 32_*).
  - `Senales_with_keys.xlsx` (resumen de señales y keys).

Uso recomendado:

- Aplicar estos archivos en SCADA siguiendo el procedimiento estándar del equipo.
- Conservar `Senales_with_keys.xlsx` como registro de lo que se creó.

---

## Eliminar señales

Resultados típicos:

- Carpeta:
  - `out/Delete/`
- Archivos:
  - `Delete_scada.csv`
  - `change_key.csv`
  - `Delete_controls.csv`

Uso recomendado:

- Revisar cuidadosamente las señales marcadas para eliminación.
- Aplicar los archivos en SCADA según los procedimientos internos.

---

## Cambiar nombre de señales

Resultados típicos:

- Carpeta:
  - `out/Name/` (o similar, según configuración).
- Archivos:
  - `change_key.csv` u otros archivos que contienen las operaciones de cambio de nombre.

Uso recomendado:

- Revisar que los nuevos nombres cumplan las convenciones de naming.
- Conservar los archivos de salida como evidencia de cambios.

---

## Errores frecuentes y consejos

- **Errores de validación (`scan_data`)**:
  - Revisa el archivo de errores (por ejemplo, `out/validacion_errores.txt`).
  - Corrige el Excel de entrada antes de reintentar.

- **Archivos de salida no generados**:
  - Comprueba la consola para ver en qué etapa falló.
  - Revisa los logs asociados (`Scada_load.log`, etc.) en la carpeta `log/`.

- **Datos SCADA viejos**:
  - Ejecuta “Actualizar datos” desde la pantalla de bienvenida o usa “Actualizar BD” en Jobs antes de lanzar operaciones críticas.

Siempre que hagas cambios masivos (crear, eliminar, renombrar):

- Trabaja primero en ambientes de prueba.
- Documenta el lote de cambios con los archivos de salida correspondientes.

