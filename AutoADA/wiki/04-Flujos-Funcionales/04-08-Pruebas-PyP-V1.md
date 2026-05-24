# 04-08 – Pruebas PyP – Versión 1

Este pipeline implementa las **Pruebas y Puesta en marcha (PyP) v1**, combinando múltiples fuentes de datos (checklist, eventos, SCADA, HIS, etc.) para generar reportes de validación y SOE.

---

## Objetivo del flujo

- Validar el comportamiento de señales y eventos antes de habilitar integraciones o cambios importantes.
- Generar:
  - Reportes SOE (Sequence of Events).
  - Checklists finales de verificación.

---

## Punto de entrada en la UI

- Vista: **Pruebas PyP** (`interfaces/marco_pruebas_pyp.py`).
- Pestaña: **Versión 1 (v1)**.
- Elementos clave:
  - Selección de **empresa**.
  - Selección de **fecha** y ventana de tiempo:
    - `pyp_fecha`, `pyp_hora_inicio`, `pyp_hora_fin`.
  - Selección de archivos:
    - Checklist.
    - EventosDiario.
    - VAREXP.
    - TMWGateway (u otros según implementación).
  - Lista de **estaciones** derivadas automáticamente (por ejemplo, desde el checklist).
  - Consola embebida.

---

## Entradas necesarias

- **Archivos de entrada**:
  - Checklist base de PyP v1.
  - Archivo(s) de eventos diarios (SOE).
  - Archivo(s) VAREXP.
  - Archivo(s) TMWGateway.
- **Datos SCADA/HIS**:
  - Accesibles a través de scripts que importan/consultan HIS/SCADA según configuración.
- **Selección de estaciones**:
  - Estaciones relevantes a incluir en la prueba.

---

## Pasos del pipeline (alto nivel)

Según la documentación, el pipeline típico v1 incluye las etapas A–E:

1. **A) IOA (direcciones)** – `scripts.itcosas_v1_ioa`
2. **B) SOE Local** – `scripts.itcosas_v1_soe_local`
3. **C) Import HIS SOE** – `scripts.import_his_soe` (opcional por estación)
4. **D) SOE Monarch** – `scripts.pyp_soe_monarch`
5. **E) Checklist final** – `scripts.pyp_checklist`

Algunas etapas se ejecutan en paralelo (especialmente A y C), otras dependen de resultados previos.

---

## Detalle de etapas

### A) IOA – Generación de direcciones (`itcosas_v1_ioa`)

- Objetivo:
  - Generar un archivo `Direcciones.csv` a partir de:
    - Archivos TMWGateway.
    - Archivos VAREXP.
  - Mapear señales a direcciones físicas/lógicas utilizadas en etapas posteriores.
- Entrada:
  - VAREXP, TMWGateway, parámetros de empresa/estación.
- Salida:
  - `Direcciones.csv` en `out/pruebas/` (u otra carpeta definida).

### B) SOE Local (`itcosas_v1_soe_local`)

- Objetivo:
  - Combinar:
    - `Direcciones.csv`.
    - Archivo de eventos diarios (SOE local).
  - Generar un SOE “local” alineado con las direcciones mapeadas.
- Entrada:
  - `Direcciones.csv`.
  - Eventos diarios.
- Salida:
  - `SOE_Local.csv` u otro nombre similar en `out/pruebas/`.

### C) Import HIS SOE (`import_his_soe`)

- Objetivo:
  - Consultar HIS para obtener SOE de una o varias estaciones dentro de la ventana de tiempo seleccionada.
- Entrada:
  - Estaciones seleccionadas.
  - Fechas y horas de inicio/fin.
- Salida:
  - `data.csv` u otro archivo con SOE desde HIS, ubicado en `out/pruebas/`.

### D) SOE Monarch (`pyp_soe_monarch`)

- Objetivo:
  - Integrar:
    - Datos SCADA.
    - Checklist base.
    - `SOE_Local.csv`.
    - `data.csv` (HIS SOE).
  - Generar un reporte SOE “Monarch” para análisis final.
- Entrada:
  - Archivos generados en etapas B y C.
  - Checklist / SCADA.
- Salida:
  - Reportes SOE en `out/pruebas/`.

### E) Checklist final (`pyp_checklist`)

- Objetivo:
  - Generar el checklist final de PyP v1:
    - Marcando resultados de pruebas.
    - Consolidando información de las etapas previas.
- Entrada:
  - Checklist base.
  - Resultados de etapas anteriores (SOE, mapeos, etc.).
- Salida:
  - Excel final del checklist en `out/pruebas/`.

---

## Comportamiento en la UI y orquestación

- Los handlers de PyP v1 (`handlers/pruebas/itcosas_v1.py`) se encargan de:
  - Validar archivos de entrada.
  - Construir comandos para cada etapa.
  - Orquestar la ejecución, lanzando etapas que pueden correr en paralelo (A y C).
  - Encadenar etapas dependientes (B, D, E) una vez disponen de los archivos previos.
- La consola:
  - Muestra prefijos como `[IOA]`, `[SOE LOCAL]`, `[HIS]`, `[SOE MONARCH]`, `[CHECKLIST]`.
  - Permite seguir el avance y detectar en qué etapa ocurrió un error.
- La barra de estado:
  - Indica la etapa actual y el estado general del pipeline.

---

## Scripts y configuraciones involucradas

- Scripts:
  - `scripts/itcosas_v1_ioa.py`
  - `scripts/itcosas_v1_soe_local.py`
  - `scripts/import_his_soe.py`
  - `scripts/pyp_soe_monarch.py`
  - `scripts/pyp_checklist.py`
- Configuración:
  - JSON en `config/` asociados a mapeos SCADA/HIS/RTU.
  - Plantillas de checklist en `templates/Checklist_V1.xlsx`.

---

## Salidas generadas

- Carpeta:
  - `out/pruebas/`
- Archivos típicos:
  - `Direcciones.csv`
  - `SOE_Local.csv`
  - `data.csv` (HIS SOE)
  - Reportes SOE Monarch.
  - Checklist final (XLSX).

Los handlers suelen presentar un diálogo final con los archivos claves para la usuaria/o.

---

## Errores comunes y recomendaciones

- **Archivos de entrada incorrectos o incompletos**:
  - Verificar que el checklist y los archivos VAREXP/TMWGateway/Eventos cumplen el formato esperado.
- **Fallas en importación HIS**:
  - Revisar credenciales ODBC/HIS y conectividad.
  - Confirmar que las estaciones seleccionadas existen y tienen datos en la ventana de tiempo indicada.
- **Resultados inconsistentes en SOE**:
  - Revisar las etapas A y B (IOA y SOE local) para verificar que las direcciones se generaron correctamente.

En caso de problemas, revisar logs específicos de PyP (si existen) y la salida detallada en la consola embebida.

