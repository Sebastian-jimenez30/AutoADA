# 08-03 – Lectura y gestión de logs

Los logs son una herramienta clave para entender qué hizo AutomatizADA y por qué algo falló. Esta página explica dónde están, cómo leerlos y cómo gestionarlos.

---

## Dónde están los logs

- Carpeta principal: `log/` junto al ejecutable o proyecto.

Ejemplos de archivos:

- `importar.log` – importaciones SCADA/HSH/ODS.
- `buscar_key.log`, `buscar_keys.log` – búsquedas de keys.
- `consultar_rtu.log` – consultas de RTU/SAS.
- otros logs específicos de scripts que usen `_Logger.py`.

Cada ejecución de un script normalmente:

- Escribe en el mismo archivo (modo append o write según configuración).
- Incluye:
  - Nivel (INFO, WARNING, ERROR...).
  - Fecha/hora.
  - Mensaje.

---

## Cuándo revisar los logs

- Cuando la consola embebida muestre errores, pero:
  - Desaparecieron del scroll.
  - Necesites más detalle.
- Cuando quieras reconstruir:
  - Qué empresas se actualizaron.
  - En qué orden se ejecutaron procesos.
  - Qué comandos se lanzaron.

`importar.log`, por ejemplo, es muy útil para entender por qué falla la actualización de datos.

---

## Cómo leerlos

Puedes abrirlos con cualquier editor de texto o visor de logs. Recomendaciones:

- Buscar por:
  - `ERROR` – para localizar fallos.
  - `WARNING` – para advertencias.
  - Nombre de empresa (ITCO, TRA, REPS, REPP) – para filtrar por empresa.
  - Nombre del script (`import_scada`, `import_hsh`, etc.).

Interpretación:

- **INFO**:
  - Mensajes de progreso normal (inicio/fin de tareas, archivos leídos).
- **WARNING**:
  - Situaciones no ideales pero no fatales (por ejemplo, archivo opcional faltante).
- **ERROR**:
  - Fallos que probablemente explican por qué el pipeline no terminó bien.

---

## Relación con la consola embebida

La consola de la UI:

- Muestra en tiempo real la salida estándar (`stdout`) de los scripts.
- Resalta:
  - Líneas con “error”, “failed” o “traceback” como **error**.
  - Líneas con “warning” como **advertencia**.

Sin embargo:

- Una vez cierras la aplicación, pierdes esa vista temporal.
- Los logs en `log/` permiten consultar la misma información (y más) después.

---

## Gestión y limpieza de logs

- Si `log/` crece demasiado:
  - Puedes archivar o eliminar logs antiguos según las políticas internas.
  - De forma manual:
    - Mover archivos antiguos a otra carpeta de archivo.
    - Borrarlos si ya no son necesarios.

Recomendaciones:

- No borrar `log/` completo si:
  - Hay procesos en curso o se planea revisar incidentes recientes.
- Etiquetar los logs archivados con:
  - Fecha.
  - Contexto (por ejemplo, “antes de upgrade X”).

---

## Buenas prácticas

- Ante incidentes:
  - Siempre adjuntar los logs relevantes al reportar el problema (ver 08-06).
- Evitar:
  - Modificar manualmente el contenido de los logs.
  - Compartir logs sin revisar si contienen información sensible (hosts, usuarios, etc.).

Con un uso adecuado de los logs, la resolución de problemas en AutomatizADA se vuelve mucho más eficiente.***
