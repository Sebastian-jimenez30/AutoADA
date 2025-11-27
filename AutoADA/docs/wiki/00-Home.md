# Automatismo ADA (AutoADA) – Portada

Bienvenida a la documentación del **Automatismo ADA (AutoADA)**, una aplicación de escritorio desarrollada para el equipo DOT Intercolombia que centraliza y automatiza tareas operativas sobre datos SCADA, HSH, ODS, pruebas PyP y consultas a RTU/SAS.

Esta wiki está pensada como el **punto único de conocimiento** del proyecto: reúne contexto de negocio, arquitectura técnica, manuales de uso, detalles de configuración y lineamientos de operación y desarrollo.

---

## ¿Qué es AutoADA?

AutoADA es una herramienta desktop (Python/Tkinter) que:

- Proporciona una **interfaz gráfica unificada** para ejecutar procesos que antes se hacían con scripts sueltos en consola.
- Coordina **importación, conversión y validación de datos** provenientes de distintos orígenes (SCADA, HSH, ODS/HIS).
- Automatiza **pipelines complejos** (Jobs, HSH, Unifilares, PyP, RTU/SAS) y entrega resultados listos para uso operativo en carpetas `out/` y bitácoras en `log/`.
- Maneja credenciales y endpoints mediante un **vault cifrado** y servicios de seguridad que restringen el uso a equipos autorizados.

En términos simples: AutoADA reduce el error humano, acelera tareas repetitivas y estandariza la generación de artefactos críticos para la operación.

---

## Audiencia de esta documentación

Esta wiki está pensada para:

- **Usuarias/os operativos DOT** que necesitan entender qué hace cada módulo y cómo usarlo con seguridad.
- **Personas de soporte y operación** que deben interpretar logs, resultados y estados de datos.
- **Desarrolladores/as** que mantienen o extienden AutoADA, y necesitan conocer la arquitectura, componentes y procesos de build.
- **Stakeholders técnicos** (líderes, arquitectos) que requieren una visión de conjunto del sistema.

Cada sección indicará claramente si está orientada a *uso operativo*, *soporte* o *desarrollo*.

---

## Cómo está organizada la wiki

La documentación se organiza por categorías. Las primeras páginas que te recomendamos leer son:

- **Resumen ejecutivo**  
  `docs/wiki/00-01-Resumen-ejecutivo.md`
- **Alcance y limitaciones**  
  `docs/wiki/00-02-Alcance-y-limitaciones.md`
- **Tecnologías y entorno**  
  `docs/wiki/00-03-Tecnologias-y-entorno.md`
- **Mapa completo de la wiki**  
  `docs/wiki/00-04-Mapa-de-la-wiki.md`

Después de esta portada, encontrarás secciones específicas para:

- Contexto de negocio y procesos que se automatizan.
- Arquitectura técnica (capas, servicios, scripts, datos).
- Flujos funcionales/pipelines (Buscar Keys, HSH, Jobs, Unifilares, PyP, RTU, etc.).
- Manual de usuario por cada pantalla.
- Seguridad, operación, soporte y desarrollo/DevOps.

---

## Por dónde empezar (según tu rol)

- **Operación / uso diario**
  - Lee primero el **Resumen ejecutivo** y el **Manual de Usuario** (sección 05 de la wiki, ver mapa).
  - Luego revisa la página de **Flujos funcionales** para entender qué pasa “por detrás”.

- **Soporte / monitoreo**
  - Revisa **Tecnologías y entorno**, **Arquitectura global** y las secciones de **Datos, Configuración y Logs**.
  - Consulta la sección de **Resolución de problemas** cuando haya incidentes.

- **Desarrollo / mantenimiento**
  - Comienza con **Arquitectura global** y **Componentes de código**.
  - Luego ve a **Desarrollo y Build** para conocer el flujo de PyInstaller, scripts de diagnóstico y patrones para agregar nuevas funcionalidades.

---

## Estado de esta documentación

Esta es una documentación **viva**. A medida que el proyecto evoluciona:

- Se actualizarán diagramas de arquitectura y flujos.
- Se registrarán nuevos pipelines y funcionalidades.
- Se ampliarán secciones de troubleshooting con casos reales.

Si detectas errores, vacíos o ideas de mejora, por favor compártelos con el equipo responsable para mantener esta wiki al día.

