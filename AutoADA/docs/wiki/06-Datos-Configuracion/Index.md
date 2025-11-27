# 06 – Datos, configuración y perfiles

Esta sección describe **cómo se organizan los datos en disco**, qué archivos de configuración existen y cómo se usan los perfiles que controlan el comportamiento de los scripts.

Está pensada para:

- Personas de soporte que necesitan entender dónde se guardan los resultados y logs.
- Desarrolladores/as que deben ajustar `config/*.json` o plantillas.
- Usuarios avanzados que quieren saber qué hay “debajo del capó” de cada módulo.

---

## Contenido de esta sección

- `06-01-Estructura-de-out-y-log.md`  
  Cómo se organizan las carpetas `out/` y `log/` y qué tipo de archivos se generan.

- `06-02-Config-import_profiles.md`  
  Explica el archivo `config/import_profiles.json` y cómo influye en `importar_all` y `Convertir_all`.

- `06-03-Config-buscar_key-y-db_names.md`  
  Describe `config/buscar_key.json` y `config/db_names.json`, claves para las búsquedas de keys.

- `06-04-Diccionario-de-tags-y-plantillas-HSH.md`  
  Resume los diccionarios y plantillas asociados a HSH.

- `06-05-Config-servers-y-dominios.md`  
  Explica `config/servers.json` y cómo se relaciona con `ServerResolver` y la UI.

- `06-06-Plantillas-Excel.md`  
  Catálogo de plantillas Excel (Jobs, HSH, PyP, etc.) y su propósito.

- `06-07-Convenciones-de-nombres-de-archivos-y-carpetas.md`  
  Convenciones usadas para nombrar archivos y carpetas en `out/` y otras rutas.

