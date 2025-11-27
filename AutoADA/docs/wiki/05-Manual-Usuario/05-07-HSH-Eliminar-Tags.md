# 05-07 – HSH: Eliminar Tags

Este módulo permite **eliminar tags existentes en HSH** basándose en un archivo Excel con la lista de tags a retirar.

---

## ¿Cuándo usarlo?

Úsalo cuando:

- Necesitas retirar tags obsoletos o que ya no deben mantenerse en HSH.
- Quieres que esta operación quede documentada en reportes.

Por tratarse de un proceso destructivo, es importante ejecutar previamente validaciones y revisar los archivos de entrada.

---

## Requisitos previos

- Excel con la lista de tags a eliminar:
  - Debe seguir la estructura acordada en tu equipo (columnas mínimas: identificador de tag, quizá key, descripción, etc.).
  - Cada fila representa un tag a eliminar.
- Datos SCADA/HSH actualizados:
  - Recomendable ejecutar validación HSH y/o “Actualizar BD” antes.

---

## Paso a paso

1. **Abrir la vista HSH**
   - En el menú lateral, abre la sección **HSH**.
   - Ve a la sección **Eliminar Tag HSH** (o equivalente en la UI).

2. **Seleccionar empresa**
   - Elige la empresa sobre la que se aplicará la eliminación.
   - Revisa las etiquetas de última actualización SCADA/HSH.

3. **Actualizar BD (opcional, recomendado)**
   - Si no estás seguro del estado de los datos:
     - Marca **Actualizar BD**.
   - AutoADA reimportará y convertirá datos SCADA/HSH para garantizar que la operación se base en información reciente.

4. **Seleccionar el archivo Excel**
   - Pulsa **Seleccionar archivo** en la sección de eliminación.
   - Elige el archivo con los tags a eliminar.
   - El botón cambiará su texto indicando que el archivo fue seleccionado.

5. **Lanzar la eliminación**
   - Pulsa el botón **Eliminar Tag HSH** (o nombre equivalente).
   - El botón se deshabilita y su texto se actualiza (por ejemplo, “Eliminando...”).
   - La consola:
     - Muestra mensajes de validación del Excel de entrada.
     - Indica qué tags se están procesando.
     - Muestra errores si algún tag no puede eliminarse o no existe.

6. **Revisar los resultados**
   - Al finalizar:
     - Se abre un diálogo de resultado:
       - Muestra uno o más archivos de reporte (por ejemplo, “eliminados”, “no eliminados”, “errores”).
       - Permite abrirlos, mostrar su carpeta o copiar sus rutas.
   - Usa estos reportes para:
     - Verificar qué tags fueron eliminados efectivamente.
     - Entender por qué algunos no se pudieron eliminar.

---

## Buenas prácticas y advertencias

- **Valida antes de eliminar**:
  - Ejecuta una validación HSH previamente para entender el estado general.

- **Revisa el Excel de entrada**:
  - Asegúrate de que:
    - Solo contiene tags que realmente deben eliminarse.
    - Los identificadores están escritos correctamente.

- **Respalda reportes**:
  - Conservar los reportes de eliminación es clave para auditoría y trazabilidad.

Si encuentras errores repetidos (por ejemplo, misma causa en muchos tags), es recomendable:

- Ajustar la fuente del problema (configuración, nombre de tags, etc.).
- Corregir el Excel y volver a ejecutar para el subconjunto afectado.

