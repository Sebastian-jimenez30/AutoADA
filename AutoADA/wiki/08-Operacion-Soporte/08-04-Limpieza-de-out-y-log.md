# 08-04 – Limpieza de `out/` y `log/`

Con el tiempo, las carpetas `out/` y `log/` pueden acumular muchos archivos. Esta página explica cómo limpiarlas sin afectar el funcionamiento de AutomatizADA.

---

## Consideraciones generales

- `out/`:
  - Contiene resultados que suelen ser útiles como evidencia o referencia.
  - Borrarlos implica perder historiales de procesos.

- `log/`:
  - Contiene bitácoras de ejecución.
  - Pueden ser voluminosas, pero son esenciales para investigar problemas.

Antes de borrar nada, evalúa si:

- Los archivos pueden necesitarse en el futuro (auditorías, análisis comparativos, etc.).
- Existe un lugar centralizado para archivar información importante.

---

## Limpieza de `out/`

En general, AutomatizADA:

- Sobrescribe algunos archivos (por ejemplo, `Find_Key.xlsx`) en ejecuciones posteriores.
- Crea nuevas carpetas para otras ejecuciones (por ejemplo, `Validaciones_<EMPRESA>`).

Estrategias de limpieza:

1. **Archivar resultados importantes**:
   - Mover carpetas/archivos clave (por ejemplo, reportes de PyP o validaciones críticas) a:
     - Una carpeta de archivo con fecha, ejemplo:
       - `out_archivo/2025-11-15_Validaciones_ITCO/`
     - Un repositorio documental corporativo.

2. **Eliminar resultados antiguos no necesarios**:
   - Borrar carpetas de `out/` relacionadas a:
     - Pruebas ya analizadas.
     - Ejecuciones de prueba sin valor actual.
   - Ejemplos:
     - Limpiar `out/pruebas/` de pruebas muy antiguas.
     - Eliminar subcarpetas `Validaciones_<EMPRESA>` obsoletas después de archivar.

Precauciones:

- No borrar `out/<EMPRESA>/SCADA`, `out/<EMPRESA>/HSH` o `out/<EMPRESA>/ODSTXT` si:
  - Se van a usar para procesos futuros, a menos que sepas que vas a reimportar de inmediato.

---

## Limpieza de `log/`

Los archivos de `log/` suelen seguir creciendo con cada ejecución. Para mantenerlos manejables:

1. **Archivado periódico**:
   - Mover logs mayores a cierta antigüedad a una carpeta de archivo:
     - Ejemplo:
       - `log_archivo/2025-11_importar.log`
   - Opcionalmente, comprimir (`.zip`) para ahorrar espacio.

2. **Eliminación de logs irrelevantes**:
   - Borra logs viejos de:
     - Pruebas.
     - Incidentes ya resueltos, si tu política lo permite.

No recomendado:

- Borrar logs recientes justo después de un fallo:
  - Podrías perder información necesaria para análisis.

---

## ¿Qué pasa si se borran `out/` y `log/` completos?

- `log/`:
  - AutomatizADA volverá a crear la carpeta y nuevos logs al ejecutar scripts.
  - Perderás historial, pero el sistema seguirá funcionando.

- `out/`:
  - La ausencia de datos puede provocar:
     - Mensajes de “faltan datos locales” en módulos como Buscar Keys, HSH, Jobs, Unifilares, PyP y Consultar RTU.
     - Forzar uso de “Actualizar datos” antes de ejecutar procesos.
  - El pipeline de actualización (`importar_all` + `Convertir_all`) recreará las estructuras necesarias.

En general:

- No es grave borrar todo `out/` si inmediatamente después ejecutas “Actualizar datos” para recrear los datasets base.
- Aun así, siempre que sea posible, **archiva** antes de borrar.

---

## Buenas prácticas

- Definir una política interna de:
  - Cuánto tiempo conservar:
    - Reportes de procesos críticos.
    - Logs de ejecución.
  - Cada cuánto hacer limpieza (mensual, trimestral, después de proyectos grandes, etc.).

- Documentar:
  - Qué se ha archivado o eliminado.
  - Quién lo hizo y cuándo (especialmente para entornos regulados).

Una gestión cuidadosa de `out/` y `log/` mantiene AutomatizADA ágil y evita problemas de espacio sin sacrificar trazabilidad.

