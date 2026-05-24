# 05-04 – Buscar Keys desde Excel (modo masivo)

Este modo permite buscar **muchas keys a la vez** leyendo una columna de un archivo Excel y generando un reporte consolidado de resultados.

---

## ¿Cuándo usarlo?

Úsalo cuando:

- Tienes una lista grande de keys (por ejemplo, decenas o cientos).
- Quieres saber dónde aparece cada una sin repetir búsquedas manuales.
- Necesitas un único Excel con los resultados para compartir o archivar.

---

## Paso a paso

1. **Abrir la vista**
   - En el menú lateral, abre la sección **Buscar**.
   - Selecciona la opción **Buscar Keys (archivo)** o equivalente en la pestaña correspondiente.

2. **Seleccionar empresa**
   - En el combo **Empresa**, elige la empresa para la que quieres buscar.

3. **Elegir el archivo Excel**
   - Pulsa el botón **Seleccionar archivo**.
   - En el diálogo:
     - Navega hasta el Excel que contiene las keys.
     - Selecciónalo y confirma.
   - El botón suele cambiar de texto (por ejemplo, “Archivo seleccionado”).
   - Nota:
     - Normalmente se espera que las keys estén en la **columna A** (una por fila).

4. **Actualizar BD (opcional)**
   - Si sospechas que los datos SCADA/HSH/ODS pueden estar desactualizados:
     - Marca **Actualizar BD**.
   - AutomatizADA ejecutará la importación y conversión antes de correr la búsqueda.

5. **Ejecutar la búsqueda masiva**
   - Pulsa el botón **Buscar Keys** (o equivalente).
   - Mientras corre:
     - El botón se deshabilita y cambia de texto (“Buscando...”).
     - La consola muestra mensajes de importación/conversión si se marcó “Actualizar BD”.
     - Luego verás mensajes específicos del script de búsqueda.

6. **Revisar el resultado**
   - Al finalizar:
     - Se abrirá un diálogo de éxito con el archivo generado:
       - Normalmente `out/Find_key/Find_Key.xlsx`.
     - Botones disponibles:
       - **Abrir archivo**: abre el Excel de resultados.
       - **Mostrar carpeta**: abre la carpeta `out/Find_key`.
       - **Copiar ruta**.
   - En el Excel:
     - Verás una fila por coincidencia.
     - Cada key de tu lista aparecerá tantas veces como coincidencias haya encontrado en las distintas bases/tablas.

---

## Recomendaciones sobre el Excel de entrada

- Asegúrate de que:
  - La columna donde están las keys es la esperada (por defecto, se asume la primera columna).
  - No haya filas con texto no relacionado (títulos, notas) mezcladas en medio de las keys.
  - Las keys sigan el formato esperado (por ejemplo, `#####.##` o con `%` como comodín).

Si el script detecta problemas de formato:

- Se mostrarán errores en la consola.
- Corrige el Excel y vuelve a ejecutar.

---

## Errores frecuentes y cómo reaccionar

- **Sin empresa seleccionada**:
  - El sistema mostrará un mensaje pidiendo que selecciones una empresa antes de continuar.

- **Archivo no seleccionado**:
  - El botón de búsqueda puede seguir deshabilitado hasta que selecciones un archivo.

- **Falta de datos locales SCADA/HSH/ODSTXT**:
  - Marca “Actualizar BD” o ejecuta primero “Actualizar datos” desde la pantalla de bienvenida.

- **Excel generado pero vacío o con pocas filas**:
  - Verifica:
    - Que las keys del archivo de entrada sean correctas.
    - Que la empresa elegida tenga datos relevantes para esas keys.

En caso de duda, revisa la consola embebida y, si existen, los logs `buscar_keys.log` o `importar.log` en la carpeta `log/`.

