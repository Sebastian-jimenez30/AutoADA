# 03 – Componentes de código (arquitectura interna)

Esta sección baja un nivel respecto a *Arquitectura global* y describe **cómo se organiza el código fuente** de AutoADA:

- Qué módulos y paquetes existen.
- Qué hace cada clase o función principal.
- Cómo se relacionan a nivel de llamadas y dependencias internas.

Está pensada para personas que van a **mantener o extender** AutoADA (desarrollo, soporte avanzado).

---

## Contenido de esta sección

- `03-01-Entrypoint-y-dispatcher.md`  
  Punto de entrada `main.py`, modo dispatcher `--run`, login y cómo la CLI se integra con el ejecutable.

- `03-02-Controllers-y-routing.md`  
  `AppController`, `FrameRouter` y la lógica de navegación, estado y layout principal.

- `03-03-Views-e-interfaces-Tkinter.md`  
  Vistas en `interfaces/`, base de vistas (`BaseView`), tema y componentes UI reutilizables.

- `03-04-Servicios-transversales.md`  
  `SecurityService`, `ServerResolver` y otros servicios que encapsulan reglas de entorno/seguridad.

- `03-05-Utils-y-helpers.md`  
  `paths`, `cli`, `task_runner`, `data_checks`, `last_update`, `ui_actions`, `shell`, etc.

- `03-06-Scripts-CLI-principales.md`  
  Resumen de los scripts más importantes en `scripts/` y cómo se organizan.

- `03-07-Plantillas-y-assets.md`  
  Uso de `config/`, `templates/` y `assets/` desde el código.

- `03-08-Estado-y-modelos.md`  
  `AppState` y posibles extensiones de modelos de datos internos.

