# 05-01 – Conceptos básicos de la UI

Esta página explica los elementos comunes de la interfaz de AutomatizADA. Entenderlos hace más fácil usar cualquier módulo.

---

## Ventana principal

Al iniciar sesión correctamente, verás:

- **Barra lateral izquierda (navbar)**:
  - Logo y botón **Inicio**.
  - Secciones plegables:
    - Buscar.
    - HSH.
    - Jobs.
    - Unifilares.
    - Pruebas PyP.
    - Consultar.
  - Cada opción abre una vista distinta en el área central.

- **Área central**:
  - Cambia según la opción seleccionada.
  - Contiene formularios, botones y, casi siempre, una consola embebida.

- **Barra de estado (abajo)**:
  - Muestra mensajes sobre lo que la aplicación está haciendo.
  - Incluye una barra de progreso (indeterminada o porcentual) cuando se ejecutan procesos.

---

## Consola embebida

En la mayoría de las vistas verás una consola de texto (fondo oscuro) donde:

- Se muestran mensajes en tiempo real:
  - [IMPORT], [CONVERT], [SCAN], [HSH], [JOBS], [PYP], etc.
- Los colores indican el tipo de mensaje:
  - Blanco: información.
  - Ámbar: advertencias.
  - Rojo: errores.
- La consola se desplaza automáticamente hacia abajo (autoscroll).

Funciones útiles:

- Seleccionar texto y usar `Ctrl+C` para copiar.
- `Ctrl+A` selecciona todo el contenido.
- El contenido no se puede editar, solo leer/copiar.

---

## Botón “Detener”

En la esquina superior derecha de la consola suele aparecer un botón **Detener**:

- Sirve para **pedir que se detengan** los procesos en ejecución.
- Al pulsarlo:
  - La aplicación intenta terminar los subprocesos en curso.
  - Muestra mensajes del tipo `[runner] stop requested`.
- No todos los procesos pueden detenerse de forma inmediata, pero es la vía recomendada si algo tarda demasiado o fue lanzado por error.

---

## Barra de estado

La barra de estado, en la parte inferior, indica:

- Mensajes como:
  - “Sincronizando datos (perfil default)...”
  - “Importando datos para ITCO...”
  - “Validación HSH completada.”
  - “Error: consulta RTU terminó con errores.”
- Barra de progreso:
  - **Indeterminada** (animación continua) cuando no se conoce el porcentaje exacto.
  - **Determinada** (barra que avanza) cuando algún proceso reporta progreso concreto.

Cuando no hay tareas en ejecución:

- Normalmente muestra “Listo” o queda en estado neutro.

---

## Diálogos de éxito y mensajes

Al terminar muchos procesos, AutomatizADA mostrará un diálogo de éxito con:

- Un mensaje principal (“Proceso completado”, “Validación lista”, etc.).
- Una lista desplegable o cuadro de texto con:
  - Archivos generados (por ejemplo, Excel de resultados).
  - O la carpeta donde se encuentran.
- Botones:
  - **Abrir archivo**: lo abre con la aplicación asociada (por ejemplo, Excel).
  - **Mostrar carpeta**: abre la carpeta en el explorador de archivos.
  - **Copiar ruta**: copia la ruta al portapapeles.
  - **Cerrar**: cierra el diálogo.

Si no se pudo generar el archivo esperado:

- Se mostrará un mensaje de error o advertencia.
- En esos casos, revisa la consola embebida y los logs para más detalles.

---

## Convenciones de selección y estados

En varias vistas se repite un patrón:

- Combos con placeholder:
  - `Empresa...`, `Dominio...`.
  - Hasta que no eliges un valor distinto, algunos botones siguen deshabilitados.
- Checkboxes:
  - “Actualizar BD” fuerza reimportación/conversión de datos antes de ejecutar el proceso.
- Botones:
  - Cambian de texto mientras están trabajando:
    - “Crear señales” → “Creando...”.
    - “Buscar Keys” → “Buscando...”.
  - Vuelven a su estado original al terminar o al fallar.

Si ves un botón deshabilitado, normalmente falta:

- Seleccionar empresa/dominio.
- Seleccionar archivo(s).
- O marcar/desmarcar una opción según el flujo.

