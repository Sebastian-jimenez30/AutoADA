# 04-09 – Pruebas PyP – Versión 2

La versión 2 de las Pruebas y Puesta en marcha (PyP v2) actualiza el pipeline de v1 para adaptarse a nuevos formatos de entrada y requerimientos, manteniendo la misma idea general: combinar múltiples fuentes de datos para validar señales y eventos.

---

## Objetivo del flujo

- Ejecutar pruebas de PyP usando una variante de pipeline más reciente:
  - Nuevos formatos de checklist.
  - Variaciones en archivos de eventos o fuentes.
  - Ajustes en la generación de SOE y reportes.

---

## Punto de entrada en la UI

- Vista: **Pruebas PyP** (`interfaces/marco_pruebas_pyp.py`).
- Pestaña: **Versión 2 (v2)**.
- Elementos:
  - Similares a v1 pero adaptados a:
    - Nuevas plantillas.
    - Posibles nuevas fuentes de datos (archivos o parámetros adicionales).

---

## Entradas necesarias

- **Checklist v2**:
  - Basado en la plantilla específica para PyP v2 (si distinta de v1).
- **Archivos de eventos y datos**:
  - Variantes de:
    - Eventos diarios.
    - Datos de gateway/SCADA.
    - Otros archivos específicos de v2 (según scripts).
- **Datos SCADA/HIS**:
  - Accesibles para consultas y validaciones.

---

## Pasos del pipeline (alto nivel)

Scripts principales para PyP v2:

1. `scripts.itcosas_v2_checklist.py`
2. `scripts.itcosas_v2_soe_local.py`
3. `scripts.import_his_soe.py` (según se requiera, como en v1)
4. `scripts.itcosas_v2_soe_monarch.py`

La lógica general es similar a v1, pero con ajustes en:

- Formatos de entrada.
- Estructura de datos intermedios.
- Reglas de validación.

---

## Detalle de etapas

### Checklist v2 (`itcosas_v2_checklist`)

- Objetivo:
  - Preparar o transformar el checklist base v2 a un formato de trabajo.
- Entrada:
  - Checklist base v2.
  - Parámetros de empresa/estación/ventana temporal (si aplica).
- Salida:
  - Archivos de checklist intermedio para etapas posteriores.

### SOE Local v2 (`itcosas_v2_soe_local`)

- Objetivo:
  - Generar un SOE local adaptado a la estructura v2.
- Entrada:
  - Eventos diarios / archivos de SOE.
  - Resultados de `itcosas_v2_checklist`, según diseño.
- Salida:
  - CSV de SOE local v2 en `out/pruebas/`.

### Import HIS SOE (`import_his_soe`)

- Funciona de forma similar a v1:
  - Consulta SOE en HIS para la ventana y estaciones seleccionadas.
  - Genera `data.csv` u otros archivos de soporte.

### SOE Monarch v2 (`itcosas_v2_soe_monarch`)

- Objetivo:
  - Integrar:
    - Checklist v2.
    - SOE local v2.
    - Datos HIS (SOE importado).
    - Datos SCADA/HIS necesarios.
- Salida:
  - Reportes SOE Monarch v2 en `out/pruebas/`.

---

## Orquestación en la UI

- El handler v2 (`handlers/pruebas/itcosas_v2.py`) se encarga de:
  - Validar inputs de la pestaña v2.
  - Construir comandos para cada etapa.
  - Ejecutar pipelines con `TaskRunner`, mostrando prefijos específicos (por ejemplo, `[V2 CHECKLIST]`, `[V2 SOE LOCAL]`, `[V2 SOE MONARCH]`).
  - Sincronizar las dependencias entre scripts.

La consola embebida permite al usuario ver en qué etapa se encuentra la ejecución y dónde se produjeron errores.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts.itcosas_v2_checklist.py`
  - `scripts.itcosas_v2_soe_local.py`
  - `scripts.itcosas_v2_soe_monarch.py`
  - `scripts.import_his_soe.py`
- Configuración:
  - Plantillas y JSON de configuración específicos v2, si los hay (por ejemplo, nuevas columnas o mapeos).

---

## Salidas generadas

- Carpeta:
  - `out/pruebas/`
- Archivos:
  - Checklists v2 intermedios y finales.
  - SOE local v2.
  - Reportes SOE Monarch v2.
  - Archivos HIS de soporte (`data.csv`, etc.).

Los handlers deberían presentar al final un resumen con los archivos clave generados.

---

## Errores comunes y recomendaciones

- **Uso de plantillas v1 en v2**:
  - Verificar que el checklist y otros archivos de entrada corresponden a v2.
- **Inconsistencias entre checklist v2 y SOE local**:
  - Revisar la configuración de `itcosas_v2_checklist` y `itcosas_v2_soe_local`.
- **Problemas en SOE Monarch v2**:
  - Confirmar que las etapas previas generaron los archivos esperados.
  - Revisar la consola para identificar en qué script se produjo el error.

Como en v1, es recomendable validar estos pipelines en entornos de pruebas antes de usarlos como base para decisiones críticas.

