# 05-10 – Pruebas PyP – Versión 1 (uso de la UI)

Esta página explica cómo lanzar el pipeline de **Pruebas y Puesta en marcha (PyP) v1** desde la interfaz gráfica.

---

## ¿Cuándo usarlo?

Úsalo cuando:

- Necesitas validar el comportamiento de señales/eventos para una ventana de tiempo.
- Trabajas con la versión original del flujo de PyP (v1) y sus plantillas.

---

## Paso a paso

1. **Abrir la vista de Pruebas PyP**
   - En el menú lateral, selecciona **Pruebas PyP**.
   - Ve a la pestaña **V1** (Versión 1).

2. **Seleccionar empresa**
   - Elige la empresa sobre la que vas a ejecutar PyP.

3. **Configurar fecha y ventana de tiempo**
   - Selecciona:
     - Fecha base de las pruebas.
     - Hora de inicio y de fin.
   - Estos valores se usan, por ejemplo, para consultas a HIS y filtrado de eventos.

4. **Seleccionar archivos de entrada**
   - Utiliza los botones de la pestaña v1 para seleccionar:
     - **Checklist** base (archivo Excel con la lista de pruebas).
     - Archivo(s) de **EventosDiario**.
     - Archivo(s) **VAREXP**.
     - Archivo(s) **TMWGateway**.
   - Tras cada selección:
     - El texto del botón se actualiza.
     - La vista puede mostrar la ruta o un label con el nombre del archivo.

5. **Revisar lista de estaciones**
   - La lista de estaciones se suele derivar del checklist o de los archivos de entrada.
   - Selecciona una o varias estaciones sobre las que deseas ejecutar PyP.

6. **Ejecutar PyP v1**
   - Pulsa el botón **Ejecutar PyP v1** (nombre exacto según la UI).
   - Mientras corre:
     - El botón se deshabilita.
     - La consola muestra etapas `[IOA]`, `[SOE LOCAL]`, `[HIS]`, `[SOE MONARCH]`, `[CHECKLIST]`.
     - La barra de estado indica la etapa actual.

7. **Revisar resultados**
   - Al finalizar:
     - Se presentará un diálogo con los archivos generados en `out/pruebas/`:
       - `Direcciones.csv`.
       - `SOE_Local.csv`.
       - `data.csv` (SOE desde HIS).
       - Reportes SOE Monarch.
       - Checklist final (XLSX).
     - Podrás abrirlos, mostrar la carpeta o copiar rutas.

---

## Consejos y errores frecuentes

- **Archivos de entrada no válidos**:
  - Si algún archivo no tiene la estructura correcta:
     - La consola indicará el problema.
     - Corrige el archivo y reintenta.

- **Sin estaciones seleccionadas**:
  - La UI puede impedir lanzar el pipeline.
  - Selecciona al menos una estación.

- **Fallas en consultas HIS**:
  - Revisa conectividad y credenciales ODBC/HIS (soporte técnico).
  - Verifica que las fechas/horas estén dentro del rango donde hay datos.

En todos los casos, la consola embebida te ayudará a identificar en qué etapa se produjo un error.

