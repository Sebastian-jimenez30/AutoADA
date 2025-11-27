# 05-09 – Unifilares: Importar y validar

Este módulo permite preparar datos y ejecutar la **validación de unifilares** a partir de archivos TXT, comparándolos con datos SCADA y ODS/ODSTXT.

---

## ¿Cuándo usarlo?

Úsalo cuando:

- Necesitas validar que los unifilares reflejan correctamente la realidad de la red.
- Quieres un reporte de inconsistencias entre unifilares y datos SCADA/ODS.

---

## Paso a paso – Importar y convertir datos

1. **Abrir la vista Unifilares**
   - En el menú lateral, selecciona **Unifilares**.

2. **Seleccionar empresa y dominio**
   - En los combos, elige:
     - Empresa.
     - Dominio (por ejemplo, QA, CC), según configuración.

3. **Marcar “Actualizar BD” (recomendado la primera vez)**
   - Si es la primera vez o no sabes si hay datos:
     - Marca **Actualizar BD**.
   - Esto indica a AutoADA que debe:
     - Importar datos SCADA y ODS para la empresa/dominio.
     - Convertirlos a formatos de trabajo (CSV/TXT).

4. **Lanzar importación/conversión**
   - Usa el botón indicado en la vista (por ejemplo, “Importar/Convertir”).
   - Mientras corre:
     - El botón se deshabilita.
     - La consola muestra mensajes de importación SCADA y ODS.
     - La barra de estado indica progreso.

5. **Esperar a que finalice**
   - Al terminar:
     - Se reactivan los botones de selección de archivo y “Ejecutar”.
     - Las etiquetas de última actualización se actualizan.

---

## Paso a paso – Validar unifilares

1. **Seleccionar archivos TXT de unifilares**
   - Pulsa el botón **Seleccionar archivos**.
   - En el diálogo:
     - Elige uno o varios archivos `.txt` de unifilares.
   - El botón indicará que hay archivos seleccionados.

2. **Verificar que los botones se habilitan correctamente**
   - Si están seleccionados:
     - Empresa.
     - Dominio.
     - Archivos TXT.
   - El botón **Ejecutar** debería habilitarse (según reglas de la vista).

3. **Ejecutar la validación**
   - Pulsa **Ejecutar**.
   - Mientras corre:
     - La consola muestra el avance:
       - Lectura de archivos TXT.
       - Uso de datos SCADA/ODSTXT.
       - Registro de hallazgos.
     - La barra de estado marca el proceso en curso.

4. **Revisar resultados**
   - Al terminar:
     - Se abrirá un diálogo de resultados con:
       - Lista de reportes generados (típicamente Excel) en:
         - `out/Validacion_Unifilares/`.
       - Botones para abrirlos, mostrar carpeta, copiar rutas.
   - En los Excel:
     - Verás detalles de inconsistencias, matches, etc., según el diseño del script.

---

## Buenas prácticas y errores comunes

- **Selecciona correctamente empresa/dominio**:
  - La validación se basa en datos SCADA/ODS específicos de esa combinación.

- **Archivos TXT incorrectos**:
  - Si la consola indica problemas al leerlos:
    - Verifica formato, codificación y estructura.

- **Datos SCADA/ODSTXT desactualizados**:
  - Vuelve a marcar **Actualizar BD** y repite el proceso de importación/conversión.

Como en otros módulos, la consola y los logs son tu primera fuente para entender qué pasó si algo falla.

