# 01-01 – Equipo y stakeholders

## Roles principales

### Operación DOT / Usuarios finales

Son las personas que **usan AutoADA en el día a día** para ejecutar tareas relacionadas con:

- Preparar y validar datos de **SCADA** y **HSH**.
- Ejecutar **Jobs** (crear, eliminar y renombrar señales).
- Realizar **validaciones de unifilares**.
- Correr **Pruebas y Puesta en marcha (PyP)**.
- Generar reportes de **RTU/SAS**.

Responsabilidades:

- Usar la herramienta siguiendo los procedimientos definidos.
- Verificar que los datos estén actualizados antes de lanzar procesos pesados.
- Revisar los resultados y reportes generados, aplicando el criterio operativo.
- Reportar incidencias o comportamientos inesperados al equipo de soporte.

### Soporte técnico / Operación avanzada

Perfil con más conocimientos técnicos, que ayuda a:

- Revisar **logs** (`log/*.log`) y diagnósticos cuando algo falla.
- Validar que las importaciones y conversiones se realizaron correctamente.
- Asistir a usuarias/os en la interpretación de mensajes de error o advertencias.
- Coordinar la ejecución de procesos especiales (por ejemplo, regeneración de vaults, limpieza de `out/` y `log/`, pruebas de conectividad a servidores).

Responsabilidades:

- Mantener la herramienta operativa en los equipos aprobados.
- Ayudar a priorizar nuevas necesidades y cambios, en coordinación con desarrollo.
- Asegurar que los lineamientos de seguridad y acceso a datos se cumplan.

### Desarrollo / Mantenimiento de AutoADA

Personas encargadas de **evolucionar el código** y mantener la calidad técnica del proyecto:

- Agregar nuevos casos de uso (módulos en la UI, handlers, scripts).
- Ajustar configuraciones (`config/*.json`) según los cambios en sistemas externos.
- Mejorar el rendimiento y la robustez de pipelines existentes.
- Asegurar compatibilidad con nuevas versiones de dependencias o entornos.

Responsabilidades:

- Seguir los patrones de arquitectura definidos (capas, handlers, TaskRunner).
- Mantener la documentación actualizada (esta wiki, comentarios relevantes, scripts).
- Coordinar cambios con operación para validar impactos.
- Cuidar la seguridad del código (no exponer secretos, manejar errores de forma controlada).

### Liderazgo técnico / Stakeholders de negocio

Roles de coordinación y decisión que:

- Definen las **prioridades de automatización** (qué procesos llevar a AutoADA y en qué orden).
- Evalúan el impacto de la herramienta en los indicadores del área (tiempos de ciclo, errores, retrabajos).
- Aseguran que AutoADA se alinee con las **políticas de seguridad y cumplimiento** de la organización.

Responsabilidades:

- Patrocinar el mantenimiento y evolución del sistema.
- Aprobar lineamientos de uso (quién puede usar qué, en qué entornos).
- Facilitar recursos y tiempo para pruebas y despliegues controlados.

## Relación entre roles

De forma simplificada:

- Operación usa la herramienta y provee feedback directo sobre su utilidad y problemas.
- Soporte actúa como puente entre operación y desarrollo, resolviendo incidencias y traduciendo necesidades en requerimientos concretos.
- Desarrollo implementa mejoras y correcciones, apoyándose en esta wiki para garantizar consistencia.
- Liderazgo técnico define prioridades y asegura que AutoADA siga siendo relevante y sostenible.

Comprender estos roles es clave para que la documentación (y la propia herramienta) apoye realmente las necesidades del negocio y no se limite a aspectos puramente técnicos.

