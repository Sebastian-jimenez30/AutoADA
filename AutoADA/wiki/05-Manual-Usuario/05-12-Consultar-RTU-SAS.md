# 05-12 – Consultar RTU / SAS

Esta página explica cómo usar el módulo de **Consulta RTU/SAS** para generar reportes a partir de datos SCADA ya convertidos.

---

## ¿Cuándo usarlo?

Úsalo cuando:

- Necesitas un listado o reporte detallado de una o varias RTU/SAS.
- Quieres basarte en datos SCADA sin construir consultas manuales.

---

## Paso a paso

1. **Abrir la vista Consultar**
   - En el menú lateral, selecciona **Consultar**.
   - Ve a la sección **RTU / SAS**.

2. **Seleccionar empresa**
   - En el combo de empresa, elige la empresa para la cual quieres consultar RTU/SAS.

3. **Revisar la lista de RTU/SAS**
   - La lista (listbox) debería llenarse automáticamente utilizando datos SCADA locales (por ejemplo, desde `32_6.csv`).
   - Si la lista aparece vacía:
     - Verifica que has actualizado SCADA para la empresa.
     - Revisa “Actualizar datos” o consulta con soporte.

4. **Seleccionar uno o varios RTU/SAS**
   - En la lista:
     - Haz clic en las RTU/SAS de interés.
     - Usa `Ctrl` o `Shift` para seleccionar múltiples elementos, según configuración de la lista.

5. **Lanzar la consulta**
   - Pulsa el botón **Consultar RTU/SAS**.
   - Mientras se ejecuta:
     - El botón se deshabilita y su texto cambia (por ejemplo, “Consultando...”).
     - La consola muestra mensajes de progreso (“Leyendo CSV”, “Procesando RTUs”, etc.).
     - La barra de estado indica que la consulta está en curso.

6. **Revisar resultados**
   - Al finalizar:
     - Si todo salió bien:
       - La barra de estado indicará “Consulta RTU lista”.
       - Se abrirá un diálogo de éxito:
         - Mostrará el archivo de reporte generado (típicamente un Excel).
         - Podrás abrir el archivo, mostrar su carpeta o copiar la ruta.
     - Si hubo errores:
       - Verás un mensaje de error.
       - Revisa la consola para ver detalles (por ejemplo, archivos SCADA faltantes o problemas de formato).

---

## Consejos y errores frecuentes

- **Sin RTU/SAS seleccionadas**:
  - El módulo mostrará un mensaje pidiendo que selecciones al menos una RTU/SAS antes de continuar.

- **Lista de RTU/SAS vacía**:
  - Asegúrate de que:
    - Se han importado y convertido los CSV SCADA para la empresa.
    - No hubo errores en procesos previos (ver “Actualizar datos” y la sección de Jobs).

- **Reportes inesperados**:
  - Si los resultados no son los esperados:
    - Verifica qué RTU/SAS fueron seleccionadas.
    - Revisa la versión y estructura de los CSV SCADA.

Conserva los reportes generados como referencia para análisis posteriores o para compartir con otros equipos.

