# 00-02 – Alcance y limitaciones

## Alcance funcional

AutoADA cubre los siguientes procesos de manera integrada:

- **Sincronización de datos operativos**:
  - Importación de datos SCADA, HSH y ODS desde servidores definidos en `config/servers.json`.
  - Conversión de esos datasets a formatos de trabajo (`CSV`, `TXT`, `XLSX`) bajo `out/<EMPRESA>/`.
- **Búsqueda de claves (Keys)**:
  - Búsqueda de una o múltiples keys en distintas fuentes (tablas SCADA, colecciones HSH, archivos ODS/ODSTXT) según diccionarios de configuración.
- **Gestión de tags HSH**:
  - Validación masiva de tags.
  - Creación de nuevos tags a partir de plantillas Excel.
  - Cambios y eliminación de tags existentes, respetando reglas de negocio.
- **Gestión de Jobs SCADA**:
  - Creación, eliminación y cambio de nombre de señales.
  - Generación de archivos de carga/descarga para SCADA según formatos estándar.
- **Validación de unifilares**:
  - Uso de datos SCADA y ODS/ODSTXT para validar consistencia de unifilares.
- **Pruebas PyP**:
  - Pipelines v1 y v2 que combinan distintos archivos de entrada (Checklist, eventos, VAREXP, TMWGateway, etc.) para generar reportes finales.
- **Consultas RTU/SAS**:
  - Generación de reportes por RTU/SAS apoyándose en los CSV SCADA ya convertidos.

## Alcance técnico

- **Tipo de aplicación**: desktop GUI basada en Tkinter, ejecutable como script (`python main.py`) o como EXE empaquetado.
- **Plataforma principal**: Windows (soportado por uso de PyInstaller, ODBC, rutas `%LOCALAPPDATA%`).
- **Modo de ejecución de lógica pesada**:
  - Scripts CLI en `scripts/` ejecutados como subprocesos.
  - Concurrencia controlada mediante `TaskRunner` para no bloquear la UI.
- **Persistencia**:
  - No mantiene un “estado persistente” centralizado propio (no DB interna). 
  - Trabaja principalmente con archivos locales (`out/`, `log/`, dumps en AppData).

## Lo que AutoADA **no** es

Para evitar malentendidos, AutoADA **no**:

- Es un SCADA ni un HMI: no muestra en tiempo real el estado de la red ni controla equipos.
- Sustituye a HSH/Historian ni a sistemas HIS: solo consume datos/provee reportes.
- Es un gestor de base de datos genérico: su lógica está orientada a casos de uso DOT específicos.
- Garantiza por sí solo la integridad de datos en sistemas externos: depende de las fuentes y de la calidad de las entradas.
- Es una plataforma multiusuario concurrente con sesiones independientes: se ejecuta en un equipo y sesión concreta.

## Limitaciones operativas

- **Equipos autorizados**:
  - El uso está restringido a hostnames autorizados (según `SecurityService`).
  - En equipos fuera de lista, la aplicación puede no iniciarse o funcionar en modo limitado.
- **Dependencia de conectividad**:
  - Muchos procesos requieren conexión a servidores remotos (SSH, Mongo, ODBC/HIS).
  - Si la conectividad es limitada o inestable, las importaciones pueden fallar o ser lentas.
- **Actualidad de datos**:
  - Los resultados dependen de que los datos locales estén sincronizados.
  - Es responsabilidad de operación ejecutar actualizaciones cuando corresponda.
- **Calidad de entradas (archivos Excel/CSV)**:
  - Los scripts asumen que los archivos de entrada cumplen plantillas y formatos especificados.
  - Archivos incompletos o modificados fuera de estándar pueden generar errores o resultados inesperados.

## Limitaciones técnicas conocidas

- **Plataforma**:
  - El soporte principal está orientado a Windows; otras plataformas no son prioridad ni están probadas a fondo.
- **Escalabilidad**:
  - Diseñado para funcionar en una estación de trabajo, no como servicio distribuido.
  - Ejecutar múltiples pipelines simultáneos puede saturar recursos locales (CPU/IO).
- **Trazabilidad externa**:
  - Los logs son locales a la máquina; si se requiere centralización/logging corporativo, debe implementarse fuera de AutoADA.

## Responsabilidades compartidas

La automatización que aporta AutoADA debe complementarse con:

- Procedimientos operativos del equipo DOT (revisión de resultados, aprobaciones).
- Mecanismos de respaldo/versionado de archivos de salida cuando sean críticos.
- Políticas de seguridad y acceso a servidores externos definidas por la organización.

Estas responsabilidades no se cubren automáticamente por la herramienta y deben quedar claras en los procesos internos.

