# 05-13 – Actualizar datos desde la pantalla de bienvenida

Aunque la actualización global de datos ya se describió en otras secciones, esta página resume el uso de **“Actualizar datos”** específicamente desde la pantalla de bienvenida para usuarias/os.

---

## ¿Qué hace “Actualizar datos”?

Cuando pulsas este botón en la pantalla de bienvenida:

- AutomatizADA sincroniza los datos locales para **todas las empresas permitidas** en tu equipo:
  - Importa SCADA, HSH y ODS desde servidores configurados.
  - Convierte estos datos a CSV/TXT bajo `out/<EMPRESA>/`.
- Deja listos los datos para que:
  - Buscar Keys.
  - HSH.
  - Jobs.
  - Unifilares.
  - PyP.
  - Consultar RTU/SAS.
  trabajen sobre información actualizada.

---

## Cuándo usarlo

Se recomienda usarlo:

- Al inicio de la jornada o de un bloque de trabajo.
- Antes de ejecutar procesos pesados o críticos (por ejemplo, grandes Jobs o PyP).
- Cuando sospeches que los datos han cambiado significativamente en los sistemas fuente.

No es necesario ejecutarlo antes de **cada** acción, pero sí mantener una periodicidad razonable según las necesidades del área.

---

## Paso a paso

1. **Ir a la pantalla de bienvenida**
   - Si no estás en ella:
     - En el menú lateral, haz clic en **Inicio**.

2. **Revisar el estado de datos**
   - Observa:
     - Para SCADA, HSH, ODSTXT:
       - La fecha/hora de última actualización.
       - “Hace cuánto” se actualizaron.
       - Para qué empresa se detectó la última actualización.

3. **Pulsar “Actualizar datos”**
   - Haz clic en el botón **Actualizar datos**.
   - Mientras se ejecuta:
     - El botón se deshabilita y cambia el texto (por ejemplo, “Actualizando...”).
     - La barra de estado muestra mensajes de progreso.
     - Los logs de importación se van escribiendo (pueden verse en la consola o luego en `log/importar.log`).

4. **Esperar a que termine**
   - Al finalizar:
     - El botón vuelve a su texto original y se habilita.
     - La barra de estado indica si:
       - Todas las empresas se actualizaron bien.
       - Hubo errores en alguna.
     - Suele mostrarse un diálogo de resumen con:
       - Empresas actualizadas.
       - Empresas con errores.
       - Ruta al log de importación.

5. **Refrescar las etiquetas de estado**
   - La pantalla de bienvenida se actualiza automáticamente.
   - Si quieres forzar un recalculo, puedes pulsar también **Refrescar estado**.

---

## Qué hacer si hay errores

Si el resumen indica que hubo empresas con errores:

- Revisa el mensaje detallado en el diálogo.
- Abre el log de importación (`importar.log`) para ver:
  - En qué empresa y etapa falló (IMPORT, CONVERT, etc.).
  - Mensajes de error o advertencia.
- Si el problema persiste, contacta a soporte técnico con:
  - El log.
  - La empresa/dominio implicados.

Mientras tanto, los datos de las empresas que **sí** se actualizaron pueden usarse normalmente.

