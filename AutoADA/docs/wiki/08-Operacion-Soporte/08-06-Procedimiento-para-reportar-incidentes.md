# 08-06 – Procedimiento para reportar incidentes

Cuando AutoADA presenta problemas que no puedes resolver con las guías de esta wiki, es importante **reportarlos correctamente** para que el equipo de soporte/desarrollo pueda ayudar de forma eficiente.

---

## 1. Reunir información básica

Antes de reportar, asegúrate de tener:

- Información del entorno:
  - Ubicación (ITCO, REP, otra).
  - Equipo (hostname).
  - Versión de AutoADA (si se expone en la UI o documentación de despliegue).

- Información del usuario:
  - Nombre y área.
  - Rol (operación, soporte, otro).

---

## 2. Describir el problema

Incluye:

- Qué estabas intentando hacer:
  - Módulo (Buscar Keys, HSH Crear, Jobs, Unifilares, PyP, RTU, etc.).
  - Empresa/dominio seleccionados.
  - Archivos usados (nombres y, si es posible, copias o ubicaciones).

- Qué esperabas que pasara:
  - Por ejemplo: “Esperaba que se generara el Excel de resultados”.

- Qué sucedió realmente:
  - Mensajes de error en la pantalla o consola.
  - Conductas extrañas (congelamientos, cierres inesperados).

Más concreta y detallada sea la descripción, más fácil será reproducir el problema.

---

## 3. Adjuntar evidencias

Siempre que sea posible, adjunta:

- **Capturas de pantalla**:
  - Del mensaje de error.
  - De la vista de la UI donde ocurrió.

- **Logs** relevantes:
  - `log/importar.log` para problemas de actualización de datos.
  - `log/buscar_key.log` o `log/buscar_keys.log` para problemas en búsquedas.
  - `log/consultar_rtu.log` para problemas en consultas RTU/SAS.
  - Cualquier otro log que parezca relacionado (por nombre/fecha/hora).

- **Archivos de entrada**:
  - Excel o TXT que se usaron cuando ocurrió el problema.
  - Si contienen información sensible, seguir las políticas internas (anonimizar, compartir por canal seguro, etc.).

---

## 4. Indicar si el problema es reproducible

Especificar:

- ¿Pasa siempre que ejecutas los mismos pasos?
- ¿Pasa solo a veces?
- ¿Ocurre solo en tu equipo o también en otros?

Si es reproducible:

- Redactar una secuencia de pasos clara:
  1. Abrir AutoADA.
  2. Ir a vista X.
  3. Seleccionar empresa Y.
  4. Cargar archivo Z.
  5. Pulsar botón W.
  6. Observar error.

---

## 5. Canal de reporte

Dependiendo de cómo se organice tu equipo, el reporte puede:

- Crearse como:
  - Ticket en sistema de gestión de incidencias (ej. Azure DevOps, JIRA, Service Desk).
  - Correo a un buzón de soporte.
  - Entrada en un canal de soporte técnico.

Recomendaciones:

- Usar un asunto/título descriptivo:
  - “AutoADA – Error al validar HSH en ITCO – 2025-11-15”
- Incluir la información y evidencias descritas en los puntos anteriores.

---

## 6. Seguimiento

Una vez reportado:

- Mantener:
  - Copias de los logs originales asociados al incidente (por si se sobrescriben).
  - Archivos de entrada utilizados.

- Si el equipo de soporte solicita más información:
  - Proporcionar detalles adicionales.
  - Reintentar acciones específicas para recopilar más datos si es seguro hacerlo.

---

## 7. Cierre del incidente

Cuando el problema se resuelva:

- Registrar (en el ticket o documentación interna):
  - Causa raíz (si se conoce).
  - Solución aplicada (código, configuración, procedimientos).
  - Versión de AutoADA donde quedó solucionado (si aplica).

Esta información ayuda:

- A evitar regresiones.
- A mejorar la documentación (por ejemplo, añadiendo nuevos casos a “Problemas comunes”).

Un buen reporte de incidentes es parte clave del mantenimiento sano de AutoADA en el tiempo.***
