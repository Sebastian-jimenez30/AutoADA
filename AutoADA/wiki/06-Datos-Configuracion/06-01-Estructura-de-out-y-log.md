# 06-01 – Estructura de `out/` y `log/`

Esta página explica cómo se organizan las carpetas de salida `out/` y `log/`, que son el principal punto de contacto para resultados y registros de ejecución.

---

## Raíz de trabajo

Por diseño:

- `out/` y `log/` viven junto al ejecutable (`AutomatizADA.exe`) o al proyecto en modo desarrollo.
- La función `utils.paths.output_root()` se encarga de:
  - Detectar la carpeta correcta.
  - Crear `out/` y `log/` si no existen.

En un entorno típico verás algo como:

- `.../AutomatizADA/out/`
- `.../AutomatizADA/log/`

---

## Estructura de `out/`

`out/` agrupa resultados por tipo de proceso y, en muchos casos, por empresa:

- `out/<EMPRESA>/SCADA`  
  CSV SCADA convertidos (tablas `10_*`, `32_*`, etc.).

- `out/<EMPRESA>/HSH`  
  CSV derivados de HSH:
  - `groups.csv`
  - `lookup_table.csv`
  - Otros según scripts.

- `out/<EMPRESA>/ODSTXT`  
  Archivos ODS/ODSTXT convertidos (TXT/CSV) para unifilares, búsqueda de keys, etc.

- `out/Find_key/`  
  Resultados de búsqueda de keys:
  - `Find_Key.xlsx` (reporte consolidado).

- `out/Load/`  
  Resultados de **Jobs – Crear señales**:
  - `10_SCADA.csv`
  - `32_FEP.csv`
  - `Senales_with_keys.xlsx`

- `out/Delete/`  
  Resultados de **Jobs – Eliminar señales**:
  - `Delete_scada.csv`
  - `change_key.csv`
  - `Delete_controls.csv`

- `out/Name/` (si aplica)  
  Resultados de **Jobs – Cambiar nombre**:
  - `change_key.csv` u otros archivos de cambios.

- `out/Validaciones_<EMPRESA>/`  
  Reportes de **Validación HSH**:
  - Varios Excel con diferentes vistas de inconsistencias.

- `out/Validacion_Unifilares/`  
  Reportes de **Validación de unifilares**.

- `out/pruebas/`  
  Resultados de **Pruebas PyP** (v1 y v2):
  - `Direcciones.csv`
  - `SOE_Local.csv`
  - `data.csv` (HIS SOE)
  - Reportes SOE Monarch
  - Checklists finales.

Además de estas carpetas, pueden existir otras creadas por nuevos módulos o scripts específicos.

---

## Estructura de `log/`

`log/` contiene archivos de bitácora por proceso. Algunos ejemplos típicos:

- `importar.log`  
  - Generado por `scripts/importar_all.py`.
  - Registra importaciones de SCADA/HSH/ODS.

- `buscar_key.log`, `buscar_keys.log`  
  - Asociados a scripts de búsqueda de keys.

- `consultar_rtu.log`  
  - Generado por `scripts/consultar_rtu.py`.

Otros scripts pueden crear sus propios logs, siempre bajo `log/`, usando `_Logger`.

Uso recomendado:

- Consultar estos archivos cuando:
  - La consola no muestra suficiente contexto.
  - Se requiere un registro persistente de qué se hizo y cuándo.

---

## Relación con AppData (`db/` y `tls/`)

Aunque no están en `out/` ni `log/`, es útil recordar:

- En `%LOCALAPPDATA%\\ADA-DOT\\`:
  - `db/`:
    - Contiene dumps importados de SCADA/HSH/ODS por empresa.
  - `tls/`:
    - Almacena material TLS/credenciales temporales si es necesario.

Estos directorios se consideran **staging** y normalmente no se exploran en el día a día como parte de los resultados visibles, pero son esenciales para el funcionamiento interno.

---

## Buenas prácticas de operación

- **Mantener `out/` ordenado**:
  - Para evitar confusiones entre resultados viejos y nuevos:
    - Considera mover o renombrar carpetas de resultados críticos.
    - No mezcles manualmente archivos de pruebas con archivos productivos.

- **Gestión de `log/`**:
  - Borra o archiva logs muy antiguos según las políticas internas.
  - Conserva logs relevantes al investigar incidentes.

Entender esta estructura te ayuda a encontrar rápidamente los archivos que necesitas y a mantener el entorno de AutomatizADA limpio y manejable.

