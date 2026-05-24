# 08-05 – Resolución de problemas comunes

Esta página recopila errores frecuentes en AutomatizADA y cómo abordarlos antes de escalar al equipo de desarrollo.

---

## 1. No puedo iniciar sesión (error de vault)

**Síntomas:**

- Mensajes como:
  - “Clave incorrecta o vault corrupto.”
  - “No se encontró vault.bin” o similar.

**Posibles causas y acciones:**

- Usuario/clave del vault incorrectos:
  - Verificar mayúsculas/minúsculas y layout del teclado.
  - Confirmar con soporte si tu usuario está habilitado.
- Vault faltante o en ruta incorrecta:
  - Revisar que el exe y el vault correspondiente (`ITCO.bin`, `REPS.bin`) estén juntos según instalación.
  - Si estás en dev, revisar que `scripts/ITCO.bin` o `scripts/REPS.bin` existe.
- Ubicación desconocida:
  - Ver sección de restricciones por hostname (07-04).

Si el problema persiste, adjuntar logs e información al reportar el incidente.

---

## 2. Mensajes de “ubicación desconocida” o cierre inmediato

**Síntomas:**

- La aplicación se cierra después del login.
- Mensajes indicando que la ubicación es “Desconocido”.

**Acciones:**

- Verificar hostname del equipo:
  - Confirmar si es uno de los prefijos esperados (ITCO, REP, etc.).
- Si el hostname cambió:
  - Coordinar con soporte para actualizar `SecurityService`.

Hasta que no se ajuste, es posible que el equipo esté bloqueado para ciertos usos.

---

## 3. No se encuentran datos locales / “Actualizar BD” obligatorio

**Síntomas:**

- Módulos como Buscar Keys, Jobs o Unifilares muestran mensajes de:
  - “No se encontraron datos locales suficientes.”
  - O fuerzan el checkbox “Actualizar BD”.

**Acciones:**

- Ir a la pantalla de bienvenida:
  - Revisar estado de SCADA/HSH/ODSTXT.
- Ejecutar:
  - “Actualizar datos” desde bienvenida, o
  - “Actualizar BD” desde el módulo específico.
- Reintentar el flujo una vez completada la actualización.

Si tras la actualización sigue faltando información, revisar `importar.log`.

---

## 4. Pipelines que fallan a mitad de camino

**Síntomas:**

- Consola muestra errores (en rojo).
- No se generan archivos esperados en `out/`.

**Acciones generales:**

1. Identificar en qué etapa falló:
   - Revisar prefijos de consola (`[IMPORT]`, `[CONVERT]`, `[SCAN]`, `[HSH]`, `[JOBS]`, `[PYP]`, etc.).
2. Revisar el log asociado:
   - `importar.log`, `buscar_key.log`, `consultar_rtu.log`, etc.
3. Verificar insumos:
   - Archivos Excel correctos y basados en plantillas.
   - Parámetros en la UI (empresa, dominio, fechas, estaciones).

Si el error proviene de conectividad (timeouts, “connection refused”, etc.):

- Validar con el área de infraestructura antes de repetir muchas veces.

---

## 5. Archivos Excel de salida vacíos o casi vacíos

**Síntomas:**

- Los procesos terminan sin error, pero:
  - Los Excel de salida tienen muy pocas filas.
  - O están vacíos.

**Posibles causas:**

- Filtros demasiado restrictivos (fechas, estaciones, listas de keys).
- Datos de origen incompletos (no hay registros para la ventana seleccionada).
- Plantillas o configuraciones desalineadas (columnas cambiadas).

**Acciones:**

- Revisar entradas:
  - Ventanas de tiempo.
  - Listas de keys.
  - Estaciones seleccionadas.
- Comparar con una ejecución anterior que haya dado resultados esperados.

---

## 6. Problemas con plantillas Excel

**Síntomas:**

- Errores sobre columnas faltantes o tipos inválidos.
- Mensajes de `scan_data` indicando problemas en el archivo.

**Acciones:**

- Confirmar que se está usando la **plantilla correcta**:
  - HSH_TEMPLATE para HSH.
  - ScadaLoad para Jobs Crear.
  - Checklist_V1 / v2 para PyP según corresponda.
- Comparar el archivo actual con la plantilla:
  - Misma estructura de columnas.
  - Tipos de datos razonables.

Corregir el archivo y reintentar.

---

## 7. AutomatizADA “se cuelga” o tarda demasiado

**Síntomas:**

- La UI parece congelada.
- La barra de estado indica procesos en curso por mucho tiempo.

**Acciones:**

- Revisar:
  - Si hay mucha carga en la máquina (CPU/IO).
  - Si la red está lenta.
- Usar el botón **Detener**:
  - Ver si responde y registra `[runner] stop requested`.
- Si no responde:
  - En casos extremos, cerrar la aplicación, documentar qué se estaba haciendo, y revisar logs.

Si el problema es recurrente en ciertos flujos, incluir esa información al reportar el incidente.

---

## 8. Errores de PyInstaller / ejecutable

**Síntomas:**

- El exe no arranca.
- Aparecen mensajes de librerías faltantes.

**Acciones (para soporte/desarrollo):**

- Verificar:
  - Que el exe se generó con las especificaciones actualizadas (`AutomatizADAITCO.spec`, `AutomatizADAREP.spec`).
  - Que las librerías nativas (por ejemplo, de `pyodbc`) están incluidas.
- Probar correr `python main.py` en el entorno de desarrollo para aislar si el problema es del proyecto o solo del packaging.

---

## Próximos pasos si no se resuelve

Si después de estas acciones el problema continua:

- Recopilar:
  - Descripción clara del error.
  - Capturas de pantalla.
  - Logs relevantes.
  - Pasos exactos para reproducir.
- Seguir el **procedimiento de reporte de incidentes** descrito en la siguiente página.

