# 00-01 – Resumen ejecutivo

## Propósito del sistema

Automatismo ADA (AutomatizADA) es una aplicación de escritorio que **automatiza y estandariza** tareas operativas críticas del equipo DOT Intercolombia, principalmente sobre:

- **SCADA**: tablas de señales, jobs, controles, SOE.
- **HSH (Historian)**: creación/validación de tags, lookup tables.
- **ODS / HIS**: datos operativos históricos para validaciones y pruebas.
- **RTU/SAS**: consultas sobre equipos de campo.

El objetivo es:

- Reducir la ejecución manual de scripts y comandos aislados.
- Minimizar errores humanos y tiempos muertos.
- Unificar en una sola herramienta los flujos más usados por el equipo.

## Qué ofrece AutomatizADA

- **Interfaz gráfica unificada** (Tkinter) con menús por caso de uso:
  - Buscar Key/Keys en bases SCADA/HSH/ODS.
  - Validar y gestionar tags en HSH.
  - Crear/eliminar/cambiar nombre de señales (Jobs SCADA).
  - Validar unifilares.
  - Ejecutar pipelines de Pruebas PyP (v1 y v2).
  - Consultar RTU/SAS.
- **Automatización de pipelines**:
  - Importar datos desde servidores remotos (SCADA/HSH/ODS/HIS).
  - Convertir y normalizar esos datos en formatos de trabajo (CSV/TXT/Excel).
  - Ejecutar scripts especializados que generan reportes listos para uso operativo.
- **Gestión integral de resultados**:
  - Todos los outputs se generan en carpetas bien definidas (`out/`).
  - Los logs quedan centralizados (`log/`) para diagnóstico.
  - La UI expone rutas y accesos directos a los archivos generados.

## Beneficios clave

- **Productividad**: reduce el tiempo de preparación de datos y ejecución de procesos complejos.
- **Calidad**: disminuye errores manuales, estandariza formatos y flujos.
- **Trazabilidad**: logs unificados y reportes generados siempre en las mismas ubicaciones.
- **Seguridad**: uso de vault cifrado y validación de hostname para restringir el entorno.
- **Escalabilidad funcional**: es sencillo agregar nuevos casos de uso siguiendo los patrones existentes (vista + handler + script + config).

## Vista de alto nivel de la arquitectura

En términos generales, AutomatizADA se organiza en capas:

1. **Interfaz de usuario (UI)**  
   - Vistas Tkinter (`interfaces/*`) y componentes reutilizables (`ui/`) que definen formularios, consolas, barras de estado y diálogos.
2. **Controlador de aplicación**  
   - `AppController` coordina navegación, estado global, selección de empresa/dominio, validaciones preliminares y despacho de tareas.
3. **Handlers**  
   - Módulos en `handlers/` que preparan el contexto, validan entradas, construyen comandos CLI, lanzan subprocesos y gestionan resultados.
4. **Scripts CLI**  
   - Implementaciones intensivas en `scripts/` (importar, convertir, validar, generar reportes) que pueden ejecutarse desde la app o por consola.
5. **Servicios y utilidades**  
   - Servicios transversales (`services/`) y utilidades (`utils/`) para seguridad, resolución de servidores, rutas, ejecución asíncrona y verificaciones.

La comunicación típica es:

> Usuario → UI → AppController → Handler → TaskRunner → Script(s) → Archivos en `out/` + logs en `log/`.

## Áreas funcionales principales

1. **Actualizar datos**  
   - Sincroniza datasets SCADA/HSH/ODS desde servidores remotos para todas las empresas permitidas, generando CSV/TXT listos para análisis.
2. **Buscar Keys**  
   - Localiza claves en múltiples bases/tablas (SCADA, HSH, ODS) y genera un Excel consolidado con resultados.
3. **HSH (tags)**  
   - Validación de tags existentes y creación/cambio/eliminación de tags, con posibilidad de aplicar cambios en entornos específicos.
4. **Jobs SCADA**  
   - Creación, eliminación y renombrado de señales, generando archivos de carga/descarga para SCADA.
5. **Unifilares**  
   - Validación de unifilares a partir de archivos ODS/TXT y datos SCADA.
6. **Pruebas PyP**  
   - Pipelines v1 y v2 para validar eventos, SOE, checklist y otros reportes antes de habilitar integraciones.
7. **Consultas RTU/SAS**  
   - Generación de reportes de RTU/SAS usando datos SCADA existentes.

Cada uno de estos módulos se documenta en detalle en las secciones de **Flujos funcionales** y **Manual de Usuario**.

## Relación con sistemas externos

AutomatizADA no reemplaza sistemas como SCADA, HSH o HIS; en cambio, se posiciona como una **capa de automatización** que:

- Consume datos desde esos sistemas (vía dumps, consultas o túneles seguros).
- Aplica reglas y transformaciones específicas del dominio DOT.
- Produce artefactos (reportes, archivos de carga) que luego se usan en procesos operativos.

Esta separación permite evolucionar AutomatizADA sin modificar los sistemas fuente, y viceversa.

