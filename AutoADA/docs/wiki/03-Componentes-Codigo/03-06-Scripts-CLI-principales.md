# 03-06 – Scripts CLI principales

Los scripts en `scripts/` implementan la mayor parte de la **lógica pesada** de AutoADA: importan datos, los convierten, ejecutan validaciones y generan reportes. Esta página resume los más relevantes.

> Nota: aquí se ofrece una vista general. Los detalles de cada pipeline se cubren en la sección de *Flujos funcionales*.

---

## Orquestadores de importación y conversión

### `importar_all.py`

Rol:

- Punto central para importar datos desde sistemas externos (SCADA, HSH, ODS).

Características:

- Argumentos:
  - `hostname`, `empresa`, `modo` (p.ej. `sca,hsh,ods`).
  - `--usecase`: indica el caso de uso (buscar_keys, hsh_validar, etc.).
  - `--flex`: permite importar empresa “relacionada” cuando aplica.
- Orquesta:
  - `import_scada.run(...)`.
  - `import_hsh.run(...)`.
  - `import_ods.run(...)`.
- Logging:
  - Usa `_Logger` para escribir en `log/importar.log` y en consola.

### `Convertir_all.py`

Rol:

- Convertir dumps importados a formatos de trabajo.

Características:

- Argumentos:
  - `empresa`, `modo` (`Buscar_keys`, `Validar_HSH`, `jobs`, `unifilares`).
  - `--only`: componentes a convertir (`sca`, `hsh`, `ods`, `ods_csv`).
- Usa AppData (`db/`) como origen y `out/` como destino.
- Puede ejecutar tareas en paralelo (por ejemplo, SCADA y ODS).
- Llama a `Convertir_Unifilares` para validaciones específicas de unifilares.

---

## HSH (Historian)

### `hsh_crear_tag.py`

Rol:

- Crear tags nuevos en HSH a partir de archivos Excel.

Características:

- Lee plantillas definidas en `templates/` y configuraciones en `config/`.
- Usa `pymongo` para interactuar con Mongo.
- Puede tener modos:
  - Validación (sin aplicar).
  - Aplicación (`--apply`) según confirmación del usuario.

### `hsh_cambiar_key.py`, `hsh_eliminar_tag.py`

Rol:

- Cambiar keys y eliminar tags en HSH.

Características compartidas:

- Consumen archivos Excel preparados por el usuario o generados por otros procesos.
- Aplican reglas de negocio para asegurar consistencia.
- Generan reportes (por ejemplo, con qué tags se trabajó, resultado de cada operación).

### `validaciones_hsh.py`

Rol:

- Validar coherencia de tags HSH vs SCADA y otras fuentes.

Características:

- Consume CSV previamente convertidos.
- Genera varios reportes bajo `out/Validaciones_<EMPRESA>/`.

---

## Jobs SCADA

### `SCADA_S-A.py`

Rol:

- Crear archivos de carga para Jobs (señales) en SCADA.

Características:

- Lee archivos de entrada que describen qué señales crear.
- Usa datos SCADA convertidos para cruzar información.
- Genera:
  - CSV de carga para tablas 10_* y 32_*.
  - Excel de resumen (por ejemplo, `Senales_with_keys.xlsx`).

### `eliminar_senales_scada.py`, `cambiar_nombre_senales_scada.py`

Rol:

- Generar archivos de eliminación o cambio de nombre de señales.

Características:

- Validan archivos de entrada con señales a eliminar/renombrar.
- Generan archivos de salida bajo `out/Delete/` o `out/Name/`.

### `scan_data.py`

Rol:

- Validar archivos de entrada (principalmente Excel) antes de ejecutar Jobs.

Características:

- Revisa estructura, tipos de datos, campos obligatorios.
- Devuelve códigos de retorno específicos:
  - `0`: OK.
  - `2`: errores de validación (los handlers pueden mostrar un detalle).

---

## Unifilares

### `Validacion_unifilares.py`, `Leer_unifilares.py`

Rol:

- Procesar archivos de unifilares y datos SCADA/ODS para generar validaciones y resúmenes.

Características:

- Consumen datos SCADA/ODS convertidos (CSV/TXT).
- Generan reportes bajo `out/Validacion_Unifilares/`.

---

## Pruebas PyP

Scripts principales para PyP v1 y v2:

- `itcosas_v1_ioa.py`:
  - Genera `Direcciones.csv` usando archivos de entrada (tmwgateway, VAREXP, etc.).
- `itcosas_v1_soe_local.py`:
  - Combina direcciones y eventos diarios para crear SOE local.
- `itcosas_v2_checklist.py`, `itcosas_v2_soe_local.py`, `itcosas_v2_soe_monarch.py`:
  - Implementan la variante v2 del pipeline, con diferentes formatos de entrada.
- `pyp_checklist.py`:
  - Genera el checklist final en formato Excel.
- `pyp_soe_monarch.py`:
  - Integra datos SCADA, checklist y otros orígenes para generar reportes SOE Monarch.
- `import_his_soe.py`:
  - Importa SOE desde HIS para integrarlo en el pipeline (cuando aplica).

Todos estos scripts trabajan con múltiples archivos de entrada y producen salidas bajo `out/pruebas/`.

---

## Consultas y utilitarios

### `consultar_rtu.py`

Rol:

- Generar reportes de RTU/SAS basados en CSV SCADA (`32_*`, `10_*`, etc.).

Características:

- Lee datos desde `out/<EMPRESA>/SCADA`.
- Usa `pandas` para cruzar tablas y armar reportes.
- Emite rutas de archivos generados en stdout para que los handlers las capturen.

### `test_mongo.py`, `test_pi_query.py`

Rol:

- Scripts de diagnóstico para:
  - Probar conexión a Mongo.
  - Probar consultas a PI/HIS u otros sistemas.

Uso:

- Útiles para soporte avanzado al diagnosticar problemas de conectividad.

---

## Scripts de vault y certificaciones

- `vault_creator.py` / `vault_creatorREP.py`:
  - Herramientas para crear/actualizar vaults cifrados con secretos.
- `ITCO.bin`, `REPS.bin`:
  - Archivos de vault específicos por entorno.
- Carpeta `cifrar/`:
  - `mongo_ca.pem`, `mongo_client.pem`, `key-py.pem`:
    - Certificados y llaves usados para conexiones seguras (por ejemplo, Mongo).

---

## Resumen

- Los scripts en `scripts/` implementan casi toda la **lógica intensiva de negocio y datos**.
- La UI y los handlers se encargan de:
  - Preparar entradas.
  - Lanzar estos scripts.
  - Interpretar salidas (especialmente rutas de archivos generados y códigos de error).

Para extender AutoADA con nuevos pipelines, lo habitual es:

1. Diseñar nuevos scripts CLI (o adaptar existentes).
2. Crear handlers que los orquesten.
3. Integrarlos en la UI mediante nuevas vistas.

