# 02 – Arquitectura global

  

Esta sección explica **cómo está organizado AutomatizADA por dentro** desde el punto de vista técnico: capas, flujo de arranque, modelo de ejecución y relación con sistemas externos.

  

No entra en los detalles de cada módulo funcional (eso se cubre en *Flujos funcionales* y *Manual de Usuario*), sino que responde a:

  

- ¿Qué capas tiene el sistema y qué rol cumple cada una?

- ¿Qué pasa desde que se abre el ejecutable hasta que aparece la pantalla de bienvenida?

- ¿Cómo se ejecutan los procesos pesados sin bloquear la interfaz?

- ¿Cómo se gestionan rutas, entornos y dependencias externas?

  

---

  

## Contenido de esta sección

  

- `02-01-Vista-de-capas.md`  

  Visión general en capas: UI, controlador, handlers, scripts, servicios, utils, datos y recursos.

  

- `02-02-Flujo-de-arranque-y-login.md`  

  Paso a paso desde `main.py` hasta la carga del vault y creación del `AppController`.

  

- `02-03-Modelo-de-ejecucion-asincrona.md`  

  Cómo `TaskRunner` y los handlers coordinan subprocesos, captura de logs y estado en la UI.

  

- `02-04-Gestion-de-rutas-y-entornos.md`  

  Cómo se separan AppData, carpeta del ejecutable, proyecto en desarrollo y variables de entorno.

  

- `02-05-Vista-de-dependencias-externas.md`  

  Qué sistemas y librerías externas se utilizan (SCADA, HSH, HIS/ODS, RTU/SAS, Mongo, ODBC, SSH, TLS).

  

Se recomienda leer esta sección antes de profundizar en **Componentes de código** y **Flujos funcionales**.