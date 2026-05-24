# 06-07 – Convenciones de nombres de archivos y carpetas

AutomatizADA utiliza convenciones de nombres para que sea fácil reconocer qué hace cada archivo y a qué proceso pertenece. Esta página resume las más importantes.

---

## Carpetas por propósito

- `out/<EMPRESA>/SCADA`  
  - CSV de tablas SCADA (`10_*`, `32_*`, etc.).

- `out/<EMPRESA>/HSH`  
  - CSV de grupos y lookup tables (`groups.csv`, `lookup_table.csv`).

- `out/<EMPRESA>/ODSTXT`  
  - Archivos ODS/ODSTXT convertidos.

- `out/Find_key/`  
  - Resultados de búsqueda de keys.

- `out/Load/`  
  - Salidas de Jobs – crear señales.

- `out/Delete/`  
  - Salidas de Jobs – eliminar señales.

- `out/Name/` (si aplica)  
  - Salidas de Jobs – cambio de nombre.

- `out/Validaciones_<EMPRESA>/`  
  - Reportes de validación HSH.

- `out/Validacion_Unifilares/`  
  - Reportes de validación de unifilares.

- `out/pruebas/`  
  - Resultados de Pruebas PyP (v1 y v2).

---

## Nombres típicos de archivos de salida

- Búsqueda de keys:
  - `Find_Key.xlsx`

- Jobs – Crear:
  - `10_SCADA.csv`
  - `32_FEP.csv`
  - `Senales_with_keys.xlsx`

- Jobs – Eliminar:
  - `Delete_scada.csv`
  - `change_key.csv`
  - `Delete_controls.csv`

- Validación HSH:
  - Varios `.xlsx` en `out/Validaciones_<EMPRESA>/` (nombres definidos por los scripts).

- Unifilares:
  - Uno o varios `.xlsx` en `out/Validacion_Unifilares/`.

- PyP:
  - `Direcciones.csv`
  - `SOE_Local.csv`
  - `data.csv` (HIS SOE)
  - Checklists y reportes SOE específicos.

- Consultar RTU/SAS:
  - Archivo Excel de reporte cuya ruta se comunica con el prefijo `RTU_REPORT:` en la consola.

---

## Nombres de logs

Aunque pueden variar, algunos patrones son:

- `importar.log` – importaciones SCADA/HSH/ODS.
- `buscar_key.log`, `buscar_keys.log` – búsquedas de keys.
- `consultar_rtu.log` – consultas RTU/SAS.

Otros scripts pueden generar logs con nombres acordes al módulo.

---

## Convenciones generales

- Uso de mayúsculas/minúsculas:
  - Carpetas suelen usar nombres “TitleCase” o descriptivos (`Validaciones_ITCO`, `Validacion_Unifilares`).
  - Archivos SCADA siguen la nomenclatura `10_*`, `32_*` propia del sistema fuente.

- Separadores:
  - Guion bajo `_` se usa para unir palabras (`Senales_with_keys`, `Delete_scada`).

- Prefijos de empresa:
  - En algunas carpetas (`Validaciones_<EMPRESA>`), el nombre de la empresa se incluye para distinguir resultados.

---

## Recomendaciones

- No cambiar manualmente los nombres de archivos generados si:
  - Van a ser reutilizados por otros scripts.
  - La documentación o procedimientos internos los esperan con un nombre concreto.

- Para archivar o versionar:
  - Copia o mueve los archivos a otra ubicación (por ejemplo, una carpeta de “archivos históricos”) conservando su nombre original.
  - Añade sufijos con fecha/hora si necesitas distinguir múltiples ejecuciones.

Seguir estas convenciones facilita la identificación de resultados y reduce errores al encadenar procesos.

