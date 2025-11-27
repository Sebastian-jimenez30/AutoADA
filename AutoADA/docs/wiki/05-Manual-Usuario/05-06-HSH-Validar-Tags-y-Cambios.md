# 05-06 – HSH: Validar tags y cambios

Esta sección cubre el uso del módulo HSH para:

- **Validar tags existentes** (coherencia HSH vs SCADA/otras fuentes).
- Revisar resultados previos de **cambios de key** (a nivel de uso de la UI).

> Nota: la eliminación de tags se detalla en la página 05-07.

---

## ¿Cuándo usar “Validar HSH”?

Úsalo cuando:

- Necesitas un diagnóstico de la situación actual de tags HSH.
- Planeas cambios importantes (crear, cambiar, eliminar tags) y quieres:
  - Confirmar el estado antes.
  - Comparar resultados después.

---

## Paso a paso – Validación de tags HSH

1. **Abrir la vista HSH**
   - En el menú lateral, abre la sección **HSH**.
   - Ve a la sección o pestaña **Validar**.

2. **Seleccionar empresa (y respaldo, si aplica)**
   - En los combos de empresa:
     - Selecciona la empresa principal.
     - Opcionalmente, selecciona la empresa de respaldo (por ejemplo, ITCO↔TRA, REPS↔REPP).
   - Observa las etiquetas de última actualización SCADA/HSH para ambas.

3. **Actualizar BD (opcional, recomendado)**
   - Si los datos parecen desactualizados:
     - Marca **Actualizar BD**.
   - AutoADA:
     - Importará SCADA+HSH para empresa principal (y respaldo).
     - Convertirá los datos a CSV para validación.

4. **Lanzar la validación**
   - Pulsa el botón **Validar HSH** (nombre exacto según la UI).
   - Mientras corre:
     - El botón se deshabilita y cambia de texto (“Validando...”).
     - La consola muestra:
       - Etapas de importación (si se activó “Actualizar BD”).
       - Mensajes de la validación (`[VALIDACION HSH]` y otros).
     - La barra de estado indica el progreso.

5. **Revisar resultados**
   - Al terminar:
     - Se abre un diálogo de éxito con la lista de archivos generados, típicamente en:
       - `out/Validaciones_<EMPRESA>/`.
     - Archivos comunes (ejemplo):
       - Reporte general de inconsistencias.
       - Listados detallados por tipo de problema.
     - Puedes:
       - Abrir cada archivo.
       - Mostrar la carpeta.
       - Copiar rutas.

---

## Cómo interpretar los reportes de validación

Aunque los nombres exactos de las hojas/columnas dependen de la configuración, en general verás:

- **Tags OK**:
  - Que pasan todas las validaciones cruzadas.
- **Tags con inconsistencias**:
  - Falta de correspondencia entre HSH y SCADA.
  - Problemas de naming o tipos.
  - Diferencias entre empresa principal y respaldo.

Usa estos reportes para:

- Priorizar ajustes de tags.
- Coordinar cambios con otros equipos (SCADA, HIS, etc.).

---

## Validar cambios de key (visión de usuario)

Si has utilizado el módulo de **Cambio de Key HSH** (ver documentación técnica), la validación HSH también sirve para:

- Comparar el estado antes y después:
  - Revisando si los tags que debían cambiar efectivamente cambiaron.
  - Revisando si no se introdujeron nuevas inconsistencias.

Pasos recomendados:

1. Ejecutar validación HSH antes de aplicar cambios grandes.
2. Ejecutar el pipeline de cambio de key (ver sección de HSH – Creación/Cambio/Eliminar).
3. Ejecutar nuevamente validación HSH.
4. Comparar reportes para verificar que los problemas se resolvieron, no aumentaron.

---

## Errores frecuentes y consejos

- **Sin empresa seleccionada**:
  - La UI mostrará un mensaje indicando que selecciones una empresa.

- **Datos insuficientes para validar**:
  - Se indicará en consola si faltan CSV SCADA/HSH.
  - Solución: ejecutar “Actualizar datos” o marcar “Actualizar BD”.

- **Reportes muy grandes**:
  - Para empresas con muchos tags, los Excel pueden ser pesados.
  - Considera filtrar o trabajar por subconjuntos cuando sea posible (según configuración).

Ante errores recurrentes, revisa:

- La consola embebida.
- Logs relacionados a validaciones HSH en la carpeta `log/`.

