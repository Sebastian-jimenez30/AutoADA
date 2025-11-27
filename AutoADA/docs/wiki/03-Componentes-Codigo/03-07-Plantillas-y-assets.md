# 03-07 – Plantillas y assets

Esta página describe cómo AutoADA utiliza archivos de configuración, plantillas Excel y recursos gráficos, y cómo están conectados con el código.

---

## Configuración (`config/`)

Archivos principales:

- `buscar_key.json`:
  - Define:
    - Qué tablas y campos se consultan al buscar keys.
    - Mapeos de nombres amigables para los reportes.
- `db_names.json`:
  - Contiene nombres de bases/tablas en SCADA/HSH u otros sistemas.
- `diccionario_tags.json`:
  - Diccionarios de tags HSH, tipos, categorías, etc.
- `import_profiles.json`:
  - Perfiles de importación (por ejemplo, qué modos y orígenes se utilizan para ciertos use cases).
- `scada.json`:
  - Configuración específica de SCADA (tablas, relaciones, etc.).
- `servers.json`:
  - Mapea claves de empresa/dominio a hostnames concretos (usado por `ServerResolver`).

Uso:

- Scripts CLI leen estos JSON para saber:
  - Qué datos importar/convertir.
  - Cómo nombrar campos y tablas en los reportes.
  - A qué servidores conectarse para cada empresa/dominio.
- Handlers pueden interpretar ciertos mapeos para mostrar información más amigable en la UI.

---

## Plantillas Excel (`templates/`)

Archivos principales:

- `Checklist_V1.xlsx`:
  - Plantilla de checklist para PyP v1.
- `HSH_TEMPLATE.xlsx`:
  - Plantilla base para creación de tags HSH.
- `ProyectoPI_EstandarSenales&TAG.xlsx`:
  - Plantilla relacionada con estandarización de señales/TAGs para proyectos PI.
- `ScadaLoad.xlsx`:
  - Plantilla usada en procesos de carga de señales para SCADA.

Uso:

- Los scripts:
  - Esperan que los Excel de entrada sigan estas plantillas.
  - Pueden generar salidas basadas en copias de estas plantillas.
- El manual de usuario debe referirse explícitamente a estas plantillas para:
  - Indicar qué columnas son obligatorias.
  - Explicar el significado de cada campo.

---

## Assets gráficos (`assets/`)

Archivos principales:

- Logos:
  - `ISAlogotipo.png`
  - `LogoDOT.png`, `LogoDOT_blanco.png`, `LogoDOT_Azul.png`, etc.
- Icono:
  - `logodot.ico`: usado como icono de la ventana (y para el exe).
- Otros:
  - Imágenes complementarias utilizadas en la UI.

Uso:

- `main.py`:
  - Usa `asset_path("Logodot.ico")` para establecer el icono de la aplicación.
- `ui/components/navbar.py`:
  - Usa `asset_path("LogoDOT_blanco.png")` para mostrar el logo en el sidebar.
- `theme.py`:
  - Puede usar colores corporativos coherentes con la identidad gráfica reflejada en los assets.

---

## Rutas a recursos en código

Helpers de `utils.paths`:

- `config_path(name)`:
  - Para acceder a archivos de `config/` sin preocuparse por dev vs exe.
- `asset_path(*parts)`:
  - Para acceder a imágenes e iconos en `assets/`.

En scripts y módulos:

- Se recomienda usar estas funciones en lugar de construir rutas manualmente, para:
  - Mantener compatibilidad con el ejecutable PyInstaller.
  - Evitar problemas de `cwd` o de ubicación del exe.

---

## Buenas prácticas al modificar plantillas/configuración

- **Versionar cambios**:
  - Siempre registrar cambios en `config/*.json` y `templates/*.xlsx` vía control de versiones.
- **Documentar impacto**:
  - Cada cambio importante en configuración o plantillas debe reflejarse en:
    - Secciones relevantes de esta wiki (Datos, Flujos, Manual de Usuario).
- **Mantener compatibilidad cuando sea posible**:
  - Cuando se requiera un cambio disruptivo, considerar:
    - Nuevas versiones de plantillas (por ejemplo, `Checklist_V2.xlsx`).
    - Flags de configuración que permitan soporte temporal a versiones antiguas.

---

## Resumen

- `config/` define cómo se comportan los scripts y qué fuentes de datos usan.
- `templates/` establecen la estructura esperada de entradas/salidas en Excel.
- `assets/` proporcionan la identidad visual de la aplicación.

El código accede a estos recursos a través de helpers centralizados, lo que simplifica el mantenimiento y la portabilidad entre entornos.

