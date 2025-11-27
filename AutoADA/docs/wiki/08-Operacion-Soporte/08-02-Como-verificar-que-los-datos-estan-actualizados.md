# 08-02 – Cómo verificar que los datos están actualizados

Muchas funcionalidades de AutoADA dependen de que los datos locales (SCADA, HSH, ODSTXT) estén **recentes**. Esta página resume cómo comprobarlo.

---

## Métodos principales

Hay dos enfoques complementarios:

1. Usar la **pantalla de bienvenida** (recomendado para operación).
2. Verificar directamente la estructura de `out/` (útil para soporte/técnico).

---

## 1. Pantalla de bienvenida

Pasos:

1. Ir a **Inicio** desde el menú lateral.
2. En la tarjeta “Estado de los datos locales”, observar:
   - Para cada dataset (SCADA, HSH, ODSTXT):
     - Fecha/hora de última actualización.
     - “Hace cuánto” se actualizaron.
     - Empresa para la que se detectó la última actualización.

Interpretación:

- Si recientemente se ejecutó “Actualizar datos”:
  - Deberías ver fechas recientes para al menos una empresa.
- Si han pasado muchos días:
  - Considera ejecutar de nuevo **Actualizar datos** antes de procesos críticos.

Puedes usar el botón **Refrescar estado** para recalcular esta información sin volver a importar nada.

---

## 2. Verificación directa en `out/`

Para soporte o diagnóstico técnico, puedes:

1. Navegar a la carpeta donde vive el exe/proyecto.
2. Revisar la estructura `out/<EMPRESA>/`:
   - `out/<EMPRESA>/SCADA`:
     - Ver fechas de modificación de CSV (ej. `10_4.csv`, `32_10.csv`).
   - `out/<EMPRESA>/HSH`:
     - Ver fechas de `groups.csv`, `lookup_table.csv`.
   - `out/<EMPRESA>/ODSTXT`:
     - Ver fechas de TXT/CSV.

Si las fechas recientes coinciden con la última actualización ejecutada:

- Es buena señal de que los datos están frescos.

---

## ¿Qué pasa si no hay datos?

Escenarios:

- `out/` está vacío o faltan subcarpetas:
  - Posiblemente nunca se ha ejecutado “Actualizar datos” para esa empresa.
- Faltan archivos clave (por ejemplo, `groups.csv`):
  - Es probable que la importación HSH para esa empresa haya fallado.

Recomendaciones:

- Ejecutar “Actualizar datos” desde la pantalla de bienvenida.
- Revisar `importar.log` en la carpeta `log/` para ver qué falló.

---

## En módulos específicos (Buscador, Jobs, Unifilares...)

Algunas vistas realizan comprobaciones adicionales:

- Buscador de keys:
  - Usa `find_mode_data_ready` para decidir si hay datos SCADA/HSH/ODSTXT suficientes.
  - Si no, puede forzar o sugerir “Actualizar BD”.

- Jobs:
  - Verifican que existan CSV SCADA mínimos antes de crear/eliminar/cambiar señales.

- Unifilares:
  - Verifican la existencia de ODS/ODSTXT convertidos.

Si ves mensajes como:

- “No se encontraron datos locales suficientes”,
- “Debe actualizar BD antes de continuar”,

entonces:

- Ejecuta la opción de actualización correspondiente en la vista (checkbox + botón).

---

## Buenas prácticas

- Antes de procesos críticos, no confiar solo en la intuición:
  - Usa la pantalla de bienvenida y, si es necesario, revisa `out/<EMPRESA>/`.
- Documentar internamente:
  - La frecuencia recomendada para actualizaciones de datos según el tipo de proceso (diario, semanal, bajo demanda, etc.).

Con estos pasos, puedes asegurarte de que AutoADA trabaja sobre la información más reciente posible dentro de sus capacidades.***
