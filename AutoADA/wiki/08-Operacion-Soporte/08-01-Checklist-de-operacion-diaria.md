# 08-01 – Checklist de operación diaria

Este checklist sugiere qué revisar al inicio de la jornada o antes de ejecutar procesos importantes en AutomatizADA.

---

## Antes de iniciar AutomatizADA

- Verificar que:
  - El equipo es el **autorizado** (hostname esperado para ITCO/REP).
  - La conexión a la red corporativa está disponible.
  - Hay acceso a los servidores SCADA/HSH/ODS/HIS necesarios (según tu rol).

---

## Al iniciar sesión en AutomatizADA

1. Abrir AutomatizADA (exe o `python main.py` en dev).
2. En la ventana de login:
   - Ingresar usuario y clave del vault.
   - Confirmar que se abre la pantalla de bienvenida sin errores.
3. Si aparece algún error de vault o ubicación:
   - No insistir múltiples veces sin revisar el mensaje.
   - Ver sección de **Resolución de problemas comunes**.

---

## Revisar estado de datos

Desde la pantalla de bienvenida:

- Revisar para SCADA/HSH/ODSTXT:
  - Fecha y hora de última actualización.
  - Tiempo transcurrido (“hace X h/m/d”).
  - Empresa para la que se detectó la actualización.
- Si los datos están:
  - Muy desactualizados.
  - O vas a ejecutar procesos grandes (Jobs, PyP, validaciones masivas).
  - → Ejecutar **Actualizar datos**.

---

## Antes de correr procesos críticos

Para acciones como:

- Grandes Jobs (crear/eliminar/cambiar nombre masivamente).
- Cambios de tags HSH.
- Pruebas PyP sobre ventanas amplias.
- Validaciones intensivas de unifilares.

Recomendado:

- Confirmar que:
  - Datos SCADA/HSH/ODS están actualizados (bienvenida).
  - Tienes los **archivos Excel** correctos y según plantilla.
  - Trabajar, si es posible, primero en un **entorno de pruebas**.
  - Existe un plan de rollback (por ejemplo, respaldos de configuraciones previas).

---

## Durante la operación

- Mientras se ejecutan pipelines:
  - Supervisar la **consola embebida**:
    - Etapas: `[IMPORT]`, `[CONVERT]`, `[SCAN]`, `[HSH]`, `[JOBS]`, `[PYP]`, etc.
  - Observar la **barra de estado**:
    - Ver qué proceso está en ejecución.
  - Si un proceso tarda excesivamente:
    - Evaluar usar el botón **Detener**.
    - Revisar conectividad (pueden haber demoras por red).

---

## Al final de la jornada (opcional)

- Revisar:
  - Si hay archivos en `out/` que deben archivarse o compartirse.
  - Si los logs (`log/`) crecieron mucho:
    - Considerar archivarlos o limpiarlos según política.
- Cerrar AutomatizADA:
  - No es obligatorio, pero evita procesos colgados si el equipo hiberna/apaga.

Este checklist puede adaptarse a los procedimientos internos de DOT/Intercolombia y complementarse con listas específicas por módulo.
