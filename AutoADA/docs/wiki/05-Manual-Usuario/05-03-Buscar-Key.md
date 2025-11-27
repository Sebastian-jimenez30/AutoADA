# 05-03 – Buscar una Key (modo manual)

Esta pantalla permite buscar **una o varias keys** ingresadas manualmente y generar un Excel con todos los lugares donde aparecen en SCADA, HSH y ODS.

---

## ¿Para qué sirve?

Usa este módulo cuando:

- Necesitas saber rápidamente dónde está definida una key concreta.
- Quieres revisar cómo se propaga una señal entre distintas bases/tablas.
- Estás haciendo análisis puntuales, no masivos.

---

## Paso a paso

1. **Abrir la vista**
   - En el menú lateral, abre la sección **Buscar**.
   - Selecciona la opción **Buscar Key** (modo manual).

2. **Seleccionar empresa**
   - En el combo **Empresa**, elige la empresa sobre la que quieres buscar.
   - Hasta que no selecciones una empresa válida, el botón de buscar permanecerá deshabilitado.

3. **Escribir la(s) key(s)**
   - En el campo de texto principal, escribe:
     - Una o varias keys separadas por comas.
     - Ejemplos:
       - `12345.67`
       - `12345.67, 23456.78`
       - `12345.%` (usa `%` como comodín).
   - Formatos válidos típicos:
     - `#####.##` (5 dígitos, punto, 2 dígitos).
     - O cualquier valor con `%` (comodín).

4. **Actualizar BD (opcional)**
   - Si no estás segura/o de que los datos locales estén al día:
     - Marca **Actualizar BD**.
   - AutoADA:
     - Importará y convertirá datos SCADA/HSH/ODS para la empresa elegida antes de buscar.

5. **Lanzar la búsqueda**
   - Pulsa el botón **Buscar**.
   - Mientras corre:
     - El botón cambia de texto (por ejemplo, “Buscando...”) y se deshabilita.
     - La consola muestra etapas `[IMPORT]`, `[CONVERT]`, `[SCAN]` y similares (si aplica).
     - La barra de estado indica el progreso (“Buscando keys...”, etc.).

6. **Ver resultados**
   - Al finalizar:
     - El botón vuelve a su texto original y se habilita.
     - Se abre un diálogo de éxito:
       - Muestra la ruta del archivo generado (por defecto: `out/Find_key/Find_Key.xlsx`).
       - Ofrece:
         - **Abrir archivo** (lo abre en Excel).
         - **Mostrar carpeta** (abre la carpeta `out/Find_key`).
         - **Copiar ruta**.
   - En el Excel verás:
     - Una fila por coincidencia.
     - Para cada key:
       - En qué fuente se encontró (SCADA/HSH/ODS).
       - En qué tabla/base y con qué atributos (según configuración).

---

## Notas y errores frecuentes

- **Keys inválidas**:
  - Si alguna key no cumple el formato esperado:
    - AutoADA puede avisar que hay keys inválidas.
    - Puede ignorarlas o bloquear la búsqueda según la configuración.
  - Revisa el mensaje de error y corrige la entrada.

- **Sin datos locales suficientes**:
  - Si faltan archivos SCADA/HSH/ODSTXT:
    - Se te pedirá (o forzará) activar “Actualizar BD”.
    - Ejecuta el proceso de actualización y reintenta.

- **Excel no se genera**:
  - Si el diálogo de éxito no aparece o indica errores:
    - Revisa la consola embebida para ver en qué etapa falló.
    - Consulta los logs `buscar_key.log` o `importar.log` (si existen) en la carpeta `log/`.

Cuando tengas dudas sobre el estado de los datos, vuelve a la pantalla de bienvenida y revisa las fechas de última actualización antes de buscar keys.

