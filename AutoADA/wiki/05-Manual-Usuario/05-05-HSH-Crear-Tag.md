# 05-05 – HSH: Crear Tag

Este módulo permite **crear nuevos tags en HSH** (Historian) a partir de un archivo Excel que sigue una plantilla específica.

---

## ¿Cuándo usarlo?

Úsalo cuando:

- Debes dar de alta un conjunto de tags en HSH.
- Quieres asegurar que:
  - Se validen datos antes de aplicar.
  - Se genere un reporte de qué se creó y cómo.

---

## Requisitos previos

- Contar con un Excel basado en la plantilla `HSH_TEMPLATE.xlsx`:
  - Incluye columnas obligatorias (nombre de tag, tipo, descripciones, etc.).
  - Cada fila representa un tag a crear.
- Datos SCADA/HSH razonablemente actualizados:
  - Si no estás seguro, marca **Actualizar BD** dentro del módulo HSH.

---

## Paso a paso

1. **Abrir la vista HSH**
   - En el menú lateral, abre la sección **HSH**.
   - En la vista HSH, ve a la sección **Crear Tag HSH**.

2. **Seleccionar empresa (y respaldo, si aplica)**
   - En los combos correspondientes, selecciona:
     - Empresa principal (obligatoria).
     - Empresa de respaldo (opcional, según la configuración de tu entorno).
   - Las etiquetas de última actualización SCADA/HSH te ayudarán a saber si necesitas refrescar datos.

3. **Opcional: Actualizar BD**
   - Si los datos SCADA/HSH están desactualizados:
     - Marca el checkbox **Actualizar BD**.
   - AutomatizADA:
     - Importará y convertirá datos SCADA/HSH para la empresa (y respaldo) antes de crear tags.

4. **Seleccionar el archivo Excel**
   - Pulsa el botón **Seleccionar archivo** en la sección de creación.
   - Elige el Excel con los tags a crear (basado en `HSH_TEMPLATE.xlsx`).
   - El botón cambiará de texto indicando que hay un archivo seleccionado.

5. **Lanzar la creación de tags**
   - Pulsa el botón **Crear Tag HSH** (o similar).
   - El botón se deshabilita y cambia de texto mientras se ejecuta.
   - La consola:
     - Muestra mensajes de validación de archivo.
     - Muestra mensajes de conexión a HSH/Mongo (si aplica).
     - Indica si está en modo “simulación” o aplicando cambios de verdad.

6. **Confirmar aplicación (si el flujo la pide)**
   - Dependiendo de la configuración, puede aparecer:
     - Una confirmación antes de aplicar cambios reales en HSH.
   - Asegúrate de revisar:
     - Cantidad de tags a crear.
     - Entorno (empresa/dominio) al que se aplicarán.

7. **Revisar resultados**
   - Al finalizar:
     - Se mostrará un diálogo de éxito.
     - Habitualmente listará:
       - Reporte principal de creación (por ejemplo, detalle de tags creados).
       - Archivos auxiliares (consultas ejecutadas, info de validaciones, etc.).
     - Podrás:
       - **Abrir archivo**.
       - **Mostrar carpeta**.
       - **Copiar ruta**.

---

## Buenas prácticas y errores frecuentes

- **Excel no sigue la plantilla**:
  - El sistema puede lanzar errores sobre columnas faltantes o datos inválidos.
  - Revisa la plantilla oficial y ajusta el archivo.

- **Errores de conexión a HSH/Mongo**:
  - Verifica la conectividad a los servidores.
  - Confirma con soporte que el vault y certificados están correctos.

- **No estoy seguro si se aplicaron cambios**:
  - Revisa:
    - El reporte de salida.
    - La consola embebida.
  - Si fue un “dry-run” (sin `--apply`), verás mensajes indicando que solo se validó, no se aplicó.

Cuando estés trabajando en entornos sensibles, es recomendable:

- Validar primero en un entorno de pruebas.
- Conservar los reportes como evidencia de los cambios realizados.

