# 06-02 – `config/import_profiles.json`

El archivo `config/import_profiles.json` define **perfiles de importación y conversión** que usan los scripts `importar_all.py` y `Convertir_all.py` según el caso de uso (buscar keys, validar HSH, jobs, unifilares, etc.).

Aunque el contenido exacto puede variar, esta página explica su intención y cómo se usa.

---

## ¿Qué es un “perfil de importación”?

Es una forma de agrupar parámetros que indican:

- Qué **modos** importar (`sca`, `hsh`, `ods`, etc.).
- Qué **tablas** o **colecciones** son relevantes para un caso de uso.
- Qué se debe convertir y con qué opciones.

En lugar de codificar estos detalles en cada script, se centralizan en `import_profiles.json`.

---

## Uso en `scripts/importar_all.py`

`importar_all.py` recibe:

- `hostname`, `empresa`, `modo` (ej. `"sca,hsh,ods"`).
- `--usecase` (ej. `"buscar_keys"`, `"hsh_validar"`, `"jobs_crear_senales"`, `"validar_unifilares"`).
- `--flex` (para importar también empresa relacionada, si aplica).

Dentro del script:

- Se puede leer `import_profiles.json` para:
  - Decidir qué tablas o colecciones se importan para ese `usecase`.
  - Ajustar comportamientos especiales (por ejemplo, qué hacer con backups).

Esto permite que:

- Cambios como “añadir una tabla más para este flujo” se hagan editando el JSON, no el código.

---

## Uso en `scripts/Convertir_all.py`

`Convertir_all.py` también puede basarse en `import_profiles.json` para:

- Saber qué componentes (`sca`, `hsh`, `ods`, `ods_csv`) debe convertir para un `modo` concreto:
  - `Buscar_keys`
  - `Validar_HSH`
  - `jobs`
  - `unifilares`
- Entender qué archivos de entrada debe buscar bajo `db/<EMPRESA>/` y qué archivos de salida debe producir bajo `out/<EMPRESA>/`.

Gracias a esto, la lógica de qué convertir para cada pipeline no está dispersa, sino centralizada.

---

## Ejemplos de perfiles típicos

Aunque el contenido concreto puede cambiar, algunos perfiles conceptuales son:

- `buscar_keys`:
  - Importa: SCADA, HSH, ODS.
  - Convierte: SCADA, HSH, ODS, ODS en CSV (`ods_csv`).

- `hsh_validar`:
  - Importa: SCADA, HSH (principal y respaldo).
  - Convierte: SCADA, HSH.

- `hsh_crear_tag`:
  - Importa: SCADA, HSH necesarios para validar y crear tags.

- `jobs_crear_senales`:
  - Importa: SCADA.
  - Convierte: SCADA en modo `jobs`.

- `validar_unifilares`:
  - Importa: SCADA, ODS.
  - Convierte: ODS/ODSTXT para unifilares.

Estos nombres de usecase son los que suelen pasar los handlers a los scripts.

---

## Impacto de modificar `import_profiles.json`

Cambiar un perfil puede afectar a varios flujos:

- Si se añade una tabla a `buscar_keys`:
  - Los reportes de búsqueda pueden incluir nuevas columnas.
  - Puede requerir ajustar `buscar_key.json` y/o los scripts.

- Si se elimina un origen de un perfil:
  - Scripts que esperaban ciertos archivos podrían fallar.

Recomendaciones:

- Antes de cambiar este archivo:
  - Identificar qué módulos usan el perfil (Buscar Keys, HSH, Jobs, etc.).
  - Probar los flujos asociados en un entorno de desarrollo.
  - Actualizar la documentación si cambia el comportamiento observable.

---

## Buenas prácticas

- Mantener nombres de `usecase` claros y consistentes.
- Documentar internamente (comentarios o documentos complementarios) qué significa cada perfil.
- Evitar que un mismo flujo dependa de demasiados perfiles diferentes si no es necesario (para no complicar el mantenimiento).

Con una buena gestión de `import_profiles.json`, la evolución de AutoADA puede hacerse de forma más declarativa y menos invasiva en el código.
