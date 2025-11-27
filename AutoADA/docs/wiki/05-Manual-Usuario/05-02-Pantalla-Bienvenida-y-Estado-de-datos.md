# 05-02 – Pantalla de bienvenida y estado de datos

La pantalla de bienvenida aparece justo después de iniciar sesión. Sirve para ver de un vistazo **qué tan frescos están los datos SCADA/HSH/ODSTXT** y para lanzar una actualización global.

---

## ¿Qué muestra la pantalla?

Elementos principales:

- Título y mensaje de bienvenida.
- Tarjeta “Estado de los datos locales” con filas para:
  - **SCADA**
  - **HSH**
  - **ODSTXT**
- Cada fila indica:
  - Fecha y hora de la última actualización detectada.
  - Cuánto tiempo ha pasado (“hace 2 h 15 m”, “hace 3 d”, etc.).
  - Para qué empresa se encontró esa actualización más reciente.
- Botones:
  - **Actualizar datos**
  - **Refrescar estado**

---

## ¿Cuándo usar esta pantalla?

Úsala como referencia antes de:

- Ejecutar búsquedas de keys.
- Correr validaciones HSH.
- Ejecutar Jobs (crear/eliminar/cambiar nombre).
- Correr validaciones de unifilares.
- Ejecutar PyP.
- Consultar RTU/SAS.

Si los datos están muy desactualizados (por ejemplo, varios días), es recomendable lanzar una actualización antes de correr procesos grandes.

---

## Botón “Refrescar estado”

Este botón:

- **No** descarga datos ni ejecuta scripts.
- Solo recalcula la “última actualización” usando los archivos que ya existen en `out/<EMPRESA>/`.
- Útil cuando:
  - Se ha corrido alguna actualización desde otra vista.
  - Quieres que la pantalla de bienvenida refleje los cambios sin relanzar importaciones.

---

## Botón “Actualizar datos”

Este botón lanza el pipeline “Actualizar datos global (perfil default)”:

1. **Qué hace**:
   - Para cada empresa permitida en el equipo:
     - Resuelve el servidor remoto correspondiente.
     - Ejecuta:
       - Importación de SCADA/HSH/ODS.
       - Conversión de esos datos a CSV/TXT bajo `out/<EMPRESA>/`.

2. **Qué ves en la UI**:
   - El botón cambia a algo como “Actualizando...” y queda deshabilitado.
   - La barra de estado muestra mensajes de progreso.
   - La consola embebida (si se muestra) o el log `importar.log` registran:
     - Comandos ejecutados.
     - Etapas por empresa (IMPORT, CONVERT, etc.).

3. **Qué pasa al terminar**:
   - El botón vuelve a su texto original y se habilita.
   - La barra de estado indica si fue exitoso o hubo errores.
   - Se llama a “Refrescar estado” internamente para actualizar las etiquetas de SCADA/HSH/ODSTXT.
   - Puede abrirse un diálogo indicando:
     - Empresas actualizadas correctamente.
     - Empresas con errores.
     - Ruta al log `importar.log` (si está disponible).

---

## Buenas prácticas de uso

- Ejecutar “Actualizar datos”:
  - Al inicio de la jornada o antes de correr procesos críticos.
  - Siempre que notes diferencias sospechosas en reportes (por ejemplo, faltan señales que deberían estar).
- Evitar:
  - Ejecutarlo innecesariamente muchas veces seguidas (consume tiempo y recursos en servidores).

Si solo necesitas confirmar que los datos están recientes, usa primero “Refrescar estado” antes de lanzar otra actualización.

