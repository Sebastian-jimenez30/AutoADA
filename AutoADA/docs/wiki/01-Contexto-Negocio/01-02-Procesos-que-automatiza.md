# 01-02 – Procesos que automatiza AutoADA

Esta sección describe los **procesos de negocio** que AutoADA apoya directamente. Cada proceso se detalla a nivel funcional; los aspectos técnicos específicos se desarrollan en las secciones de Flujos funcionales y Manual de Usuario.

---

## 1. Sincronización de datos operativos

### Problema de negocio

Los equipos de operación necesitan trabajar con datos SCADA, HSH y ODS/HIS actualizados para tomar decisiones y ejecutar validaciones. Hacer esta preparación manualmente implica:

- Conectar a distintos servidores.
- Lanzar scripts o comandos con parámetros específicos.
- Copiar y transformar archivos en múltiples formatos.

### Qué aporta AutoADA

- Un flujo unificado para:
  - Importar datos desde servidores remotos por empresa.
  - Convertir esos datos a formatos de trabajo (CSV/TXT/Excel).
  - Dejar los resultados organizados en `out/<EMPRESA>/SCADA`, `out/<EMPRESA>/HSH`, `out/<EMPRESA>/ODSTXT`.
- Indicadores visuales del estado de las últimas actualizaciones (pantalla de bienvenida).

Beneficio: menos tiempo en “preparar el terreno” y más tiempo en análisis y decisiones.

---

## 2. Búsqueda de claves (Keys)

### Problema de negocio

Se requiere ubicar rápidamente **claves (keys)** en múltiples fuentes (SCADA, HSH, ODS) para:

- Entender dónde está definida una señal.
- Revisar cómo se propaga a través de diferentes bases/tablas.
- Apoyar análisis de problemas y planificación de cambios.

### Qué aporta AutoADA

- Funcionalidades de:
  - Buscar una key manualmente.
  - Buscar muchas keys a partir de un archivo Excel.
- Generación de un **Excel consolidado** que indica:
  - En qué base/tabla aparece cada key.
  - Información contextual (nombre de la señal, tipo, tabla, etc., según configuración).

Beneficio: búsquedas repetitivas se vuelven sistemáticas, trazables y mucho más rápidas.

---

## 3. Gestión de tags en HSH (Historian)

### Problema de negocio

HSH almacena grandes cantidades de tags que deben:

- Crearse de forma consistente.
- Validarse contra reglas de negocio.
- Modificarse o eliminarse cuando cambian las condiciones de operación.

Hacerlo manualmente es propenso a errores y difícil de auditar.

### Qué aporta AutoADA

- Procesos guiados para:
  - Validar tags existentes.
  - Crear nuevos tags a partir de plantillas Excel (con campos obligatorios).
  - Cambiar keys o eliminar tags de forma controlada.
- Uso de un **vault cifrado** y servidores configurados para:
  - Separar entornos (empresas/dominios).
  - Evitar que usuarios finales manipulen credenciales directamente.

Beneficio: manejo de tags más seguro, reproducible y alineado con estándares internos.

---

## 4. Gestión de Jobs SCADA (señales)

### Problema de negocio

Crear, eliminar o renombrar señales en SCADA suele involucrar:

- Manipulación de tablas específicas.
- Generación de archivos de carga siguiendo formatos estrictos.
- Validaciones previas para evitar inconsistencias.

### Qué aporta AutoADA

- Módulos dedicados a:
  - **Crear señales** (Jobs de alta frecuencia).
  - **Eliminar señales**.
  - **Cambiar nombres de señales**.
- Cada flujo:
  - Valida inicialmente los datos de entrada (Excel).
  - Utiliza datos SCADA actualizados.
  - Genera archivos de carga/descarga listos para aplicar en SCADA.

Beneficio: reduce riesgos de errores en cambios masivos de señales y estandariza el proceso.

---

## 5. Validación de unifilares

### Problema de negocio

Los unifilares deben reflejar correctamente la realidad de la red y las señales asociadas. Validarlos manualmente contra datos SCADA/ODS puede ser lento y propenso a omisiones.

### Qué aporta AutoADA

- Flujos que:
  - Importan y convierten datos relevantes de SCADA y ODS/ODSTXT.
  - Permiten seleccionar archivos de unifilares a validar.
  - Generan reportes de validación con hallazgos claros.

Beneficio: validaciones más consistentes y trazables, con reportes que se pueden compartir y archivar.

---

## 6. Pruebas y Puesta en marcha (PyP)

### Problema de negocio

Antes de habilitar nuevas integraciones o cambios importantes, se deben ejecutar **Pruebas y Puesta en marcha** que:

- Integran múltiples fuentes de datos (checklists, eventos, HIS, SCADA, etc.).
- Requieren varios pasos intermedios y archivos de salida.

Hacer esto manualmente aumenta el riesgo de pasos omitidos o ejecutados en orden incorrecto.

### Qué aporta AutoADA

- Pipelines PyP (v1 y v2) que:
  - Piden las entradas necesarias mediante formularios claros.
  - Ejecutan en el orden correcto los scripts asociados.
  - Generan reportes finales listas para revisión y archivo.

Beneficio: pruebas más repetibles, estructuradas y fáciles de auditar.

---

## 7. Consultas RTU/SAS

### Problema de negocio

Necesidad de obtener información consolidada sobre **RTU/SAS** basada en datos SCADA ya existentes, sin armar consultas ad-hoc cada vez.

### Qué aporta AutoADA

- Una interfaz para:
  - Seleccionar empresa y RTU/SAS de interés.
  - Lanzar una consulta basada en los CSV SCADA.
  - Generar reportes específicos para análisis posterior.

Beneficio: menos tiempo construyendo consultas, más tiempo analizando resultados.

---

## Visión global

En conjunto, estos procesos permiten que AutoADA:

- Sea un **hub de automatización** para tareas operativas DOT relacionadas con señales, tags, unifilares, pruebas y consultas.
- Reduzca la dependencia de scripts dispersos y conocimiento tácito.
- Alinee la operación diaria con estándares y procedimientos formalizados.

