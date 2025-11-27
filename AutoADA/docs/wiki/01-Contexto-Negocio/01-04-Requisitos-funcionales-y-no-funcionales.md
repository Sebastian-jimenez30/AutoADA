# 01-04 – Requisitos funcionales y no funcionales

Esta sección resume los requisitos que guían el diseño de AutoADA desde el punto de vista del negocio y de la operación. No pretende ser un pliego formal, sino una referencia práctica.

---

## Requisitos funcionales (qué debe hacer)

1. **Proveer una interfaz gráfica unificada**
   - RF-01: Ofrecer menús y pantallas dedicadas para cada caso de uso (Buscar Keys, HSH, Jobs, Unifilares, PyP, RTU).
   - RF-02: Permitir iniciar sesión con usuario/clave para desbloquear el vault de credenciales.

2. **Sincronizar datos operativos**
   - RF-03: Importar datos SCADA, HSH y ODS desde servidores configurados, por empresa.
   - RF-04: Convertir esos datos a formatos de trabajo (CSV/TXT/Excel) y almacenarlos en `out/<EMPRESA>/`.
   - RF-05: Mostrar al usuario el estado de actualización de los datos (última vez que se actualizaron).

3. **Buscar y analizar Keys**
   - RF-06: Permitir búsquedas manuales de una o varias keys.
   - RF-07: Permitir búsquedas masivas a partir de un archivo Excel.
   - RF-08: Generar reportes consolidados indicando en qué bases/tablas aparece cada key.

4. **Gestionar tags en HSH**
   - RF-09: Validar tags existentes contra reglas de negocio.
   - RF-10: Crear nuevos tags en HSH a partir de plantillas Excel.
   - RF-11: Permitir cambiar keys o eliminar tags con confirmaciones explícitas.

5. **Gestionar Jobs SCADA**
   - RF-12: Crear, eliminar y renombrar señales SCADA mediante flujos guiados.
   - RF-13: Validar archivos de entrada antes de generar cargas.
   - RF-14: Generar archivos de salida para carga/descarga en SCADA.

6. **Validar unifilares**
   - RF-15: Permitir importar/convertir datos necesarios para validaciones.
   - RF-16: Ejecutar validaciones de unifilares y generar reportes.

7. **Ejecutar Pruebas PyP**
   - RF-17: Implementar pipelines PyP v1 y v2.
   - RF-18: Gestionar archivos de entrada y producir reportes finales.

8. **Consultar RTU/SAS**
   - RF-19: Permitir seleccionar RTU/SAS de interés por empresa.
   - RF-20: Generar reportes de RTU/SAS basados en datos SCADA.

9. **Gestionar resultados y logs**
   - RF-21: Mostrar en la UI la ruta de los archivos generados.
   - RF-22: Mantener logs de ejecución por proceso en `log/`.
   - RF-23: Informar claramente al usuario cuando un proceso termina con éxito o con errores.

---

## Requisitos no funcionales (cómo debe hacerlo)

1. **Usabilidad**
   - RNF-01: La UI debe ser consistente (mismo estilo de botones, campos, mensajes).
   - RNF-02: Los mensajes deben estar en un lenguaje claro y alineado con el dominio DOT.
   - RNF-03: Debe minimizar la cantidad de datos que el usuario ingresa a mano (combos, plantillas, defaults).

2. **Confiabilidad**
   - RNF-04: Los procesos deben manejar errores de forma controlada, sin cerrar abruptamente la aplicación.
   - RNF-05: Los logs deben ser lo suficientemente detallados para reconstruir qué ocurrió.
   - RNF-06: Las rutas de salida deben ser determinísticas y estables en el tiempo.

3. **Rendimiento**
   - RNF-07: Los procesos pesados deben ejecutarse en segundo plano, sin congelar la UI.
   - RNF-08: Debe ser posible detener (en lo posible) procesos en curso mediante la consola embebida.

4. **Seguridad**
   - RNF-09: Las credenciales sensibles nunca deben quedar en claro en archivos de texto sin protección.
   - RNF-10: El acceso a AutoADA debe restringirse a equipos autorizados (control por hostname).
   - RNF-11: El acceso a sistemas externos debe hacerse a través de canales cifrados y certificados cuando corresponda.

5. **Mantenibilidad**
   - RNF-12: La arquitectura debe separar claramente UI, lógica de orquestación (handlers) y scripts CLI.
   - RNF-13: La configuración (servidores, perfiles, diccionarios) debe residir en archivos editables (`config/*.json`), no en constantes incrustadas.
   - RNF-14: Debe existir documentación actualizada (esta wiki) que describa flujos, componentes y procedimientos de build.

6. **Portabilidad y despliegue**
   - RNF-15: Debe poder ejecutarse tanto en modo desarrollo (Python) como en modo distribuido (EXE PyInstaller).
   - RNF-16: El ejecutable debe incluir todas las dependencias necesarias para funcionar sin instalaciones adicionales en el equipo objetivo (más allá de prerrequisitos corporativos).

---

## Uso de estos requisitos

Estos requisitos sirven como referencia para:

- Validar que los desarrollos y cambios propuestos estén alineados con las necesidades del negocio.
- Priorizar mejoras y refactorizaciones (por ejemplo, cuando se detectan problemas de usabilidad o mantenibilidad).
- Comunicar de forma clara qué se espera de AutoADA a nivel funcional y operativo.

En futuras iteraciones se pueden extender con criterios más detallados (por ejemplo, acuerdos de niveles de servicio, tiempos máximos de ejecución, métricas de calidad de datos, etc.).

