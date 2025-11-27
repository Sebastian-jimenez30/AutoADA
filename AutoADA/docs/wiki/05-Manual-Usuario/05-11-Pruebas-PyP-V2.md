# 05-11 – Pruebas PyP – Versión 2 (uso de la UI)

Esta página explica cómo usar la pestaña de **Pruebas PyP v2**. La lógica es similar a v1, pero adaptada a nuevas plantillas y scripts.

---

## ¿Cuándo usarlo?

Úsalo cuando:

- Tu proceso PyP está basado en la **versión 2** de plantillas y scripts.
- Te lo haya indicado tu equipo (por ejemplo, para nuevos proyectos o integraciones).

---

## Paso a paso

1. **Abrir la vista de Pruebas PyP v2**
   - En el menú lateral, selecciona **Pruebas PyP**.
   - Ve a la pestaña **V2**.

2. **Seleccionar empresa y parámetros básicos**
   - Elige la empresa.
   - Configura fecha y ventana de tiempo si la pestaña v2 lo requiere (depende del diseño exacto de la UI).

3. **Seleccionar archivos de entrada v2**
   - Botones típicos:
     - Checklist v2.
     - EventosDiario versión compatible.
     - Otros archivos específicos de la versión 2 (según se haya implementado).
   - Asegúrate de usar las plantillas correctas v2, no las de v1.

4. **Seleccionar estaciones (si aplica)**
   - Al igual que en v1, puede haber una lista de estaciones.
   - Selecciona las que correspondan a la prueba.

5. **Ejecutar PyP v2**
   - Pulsa el botón **Ejecutar PyP v2** (nombre exacto según la UI).
   - Mientras corre:
     - El botón se deshabilita.
     - La consola muestra las etapas específicas v2 (por ejemplo, `[V2 CHECKLIST]`, `[V2 SOE LOCAL]`, `[V2 SOE MONARCH]`).
     - La barra de estado indica el avance general.

6. **Revisar resultados**
   - Al finalizar:
     - Se abre un diálogo de resultados con archivos generados en `out/pruebas/`.
     - Entre ellos:
       - Checklists intermedios v2.
       - SOE local v2.
       - Reportes SOE Monarch v2.
       - Archivos HIS de soporte (`data.csv`, etc.), si se usaron.
     - Puedes abrir, mostrar carpeta o copiar rutas desde el diálogo.

---

## Consejos y errores frecuentes

- **Uso de plantillas incorrectas**:
  - Si usas plantillas de v1 en v2 (o viceversa), es probable que:
    - Falte alguna columna.
    - Haya errores de lectura.
  - Revisa que estés usando la versión correcta de las plantillas.

- **Errores en etapas intermedias**:
  - Si el pipeline falla en una etapa, la consola indicará en cuál:
    - `[V2 CHECKLIST]`.
    - `[V2 SOE LOCAL]`.
    - `[V2 SOE MONARCH]`.
  - Corrige según el mensaje y reintenta.

- **Resultados inesperados**:
  - Compara con los resultados de PyP v1 (cuando exista un flujo equivalente) para entender diferencias.

Ante problemas recurrentes, coordina con el equipo técnico para revisar configuraciones específicas de v2 (mapeos, plantillas, scripts).

