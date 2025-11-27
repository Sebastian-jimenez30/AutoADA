# 01-03 – Flujos antes y después de AutoADA

Esta sección compara cómo se realizaban las tareas clave **antes** de AutoADA y cómo se realizan **después**, resaltando los cambios en:

- Número de pasos manuales.
- Riesgo de error.
- Trazabilidad.

---

## Situación previa (antes de AutoADA)

Características típicas:

- Uso de **scripts sueltos** (Python, shell, consultas manuales) ubicados en distintas carpetas o equipos.
- Ejecución por consola o herramientas básicas, con:
  - Parámetros pasados a mano (host, empresa, rutas).
  - Rutas de entrada/salida poco estandarizadas.
  - Dependencia fuerte del conocimiento de unas pocas personas.
- Validaciones y combinaciones de datos (por ejemplo, para PyP o unifilares) realizadas:
  - Con hojas de cálculo manualmente.
  - Con pasos intermedios poco documentados.
- Logs de ejecución dispersos o inexistentes:
  - Difícil reconstruir qué se hizo, cuándo y con qué parámetros.

Consecuencias:

- Alto riesgo de errores manuales en parámetros y rutas.
- Dificultad para incorporar nuevas personas al proceso.
- Tiempos variables y poco predecibles de ejecución.

---

## Situación actual (con AutoADA)

Con AutoADA, la ejecución de estos procesos se centraliza en una **aplicación de escritorio con UI unificada**:

- Menús y pantallas dedicadas a cada caso de uso (Buscar Keys, HSH, Jobs, Unifilares, PyP, RTU).
- Formularios que:
  - Restringen opciones a valores válidos (empresas, dominios).
  - Validan inputs (archivos Excel, formatos de keys, fechas).
  - Deshabilitan acciones cuando faltan datos previos.
- Pipelines definidos que:
  - Ejecutan scripts en **orden correcto**.
  - Reutilizan datos previamente importados y convertidos.
  - Generan siempre outputs en ubicaciones estándar.
- Consola embebida y barra de estado que:
  - Muestran el avance y mensajes de cada etapa.
  - Resaltan errores y advertencias.

Consecuencias:

- Procesos más repetibles y predecibles.
- Menor dependencia de “memoria” y experiencia individual.
- Mejor capacidad para auditar y explicar qué se hizo.

---

## Ejemplos de transformación de flujo

### Ejemplo 1: Búsqueda de Keys

**Antes**:

- Ejecutar scripts o consultas específicas por cada fuente.
- Abrir manualmente varios archivos/tablas.
- Combinar resultados en Excel a mano.

**Después** (con AutoADA):

- Ingresar la key o seleccionar un Excel con múltiples keys.
- AutoADA:
  - Verifica que haya datos SCADA/HSH/ODS locales (y si no, permite actualizarlos).
  - Ejecuta los scripts necesarios para todas las fuentes.
  - Genera un Excel consolidado con resultados.

### Ejemplo 2: Jobs SCADA (crear señales)

**Antes**:

- Preparar archivos de entrada siguiendo plantillas internas.
- Ejecutar scripts que generaban archivos de carga.
- Verificar manualmente que no hubiera inconsistencias.

**Después**:

- Seleccionar empresa y archivo Excel de entrada.
- AutoADA:
  - Valida el archivo y sus columnas.
  - Se asegura de que existan datos SCADA actualizados.
  - Ejecuta los scripts de validación y generación de cargas en orden.
  - Entrega archivos finales en `out/Load/` con un diálogo de éxito.

### Ejemplo 3: Pruebas PyP

**Antes**:

- Varios pasos manuales con múltiples scripts y archivos intermedios.
- Fácil olvidar algún paso o usar un archivo incorrecto.

**Después**:

- Seleccionar empresa, fechas y archivos requeridos en una sola pantalla.
- AutoADA:
  - Orquesta la ejecución de scripts en el orden correcto.
  - Maneja dependencias entre etapas (archivos intermedios).
  - Presenta los reportes finales listos para revisión.

---

## Impacto esperado

Al pasar de flujos manuales dispersos a flujos centralizados en AutoADA, se espera:

- **Menos errores**: gracias a validaciones automáticas y parámetros guiados.
- **Mayor trazabilidad**: logs centralizados y outputs en rutas estándar.
- **Mejor onboarding**: nuevas personas pueden aprender los procesos a través de la UI y esta wiki, sin depender exclusivamente de scripts sueltos.
- **Mayor productividad**: más tiempo dedicado al análisis y menos a la logística de preparar y combinar datos.

