# 06-05 – `config/servers.json` (empresas y dominios)

El archivo `config/servers.json` define los **servidores remotos** asociados a cada combinación de empresa y dominio. Es clave para que AutoADA sepa a qué host conectarse al importar datos.

---

## Estructura conceptual

A alto nivel, `servers.json` suele tener una estructura similar a:

```json
{
  "1": { "1": "host_itco_qa", "2": "host_itco_cc" },
  "2": { "1": "host_tra_qa",  "2": "host_tra_cc"  },
  "3": { "1": "host_reps_qa", "2": "host_reps_cc" },
  "4": { "1": "host_repp_qa", "2": "host_repp_cc" }
}
```

Donde:

- La clave externa (`"1"`, `"2"`, `"3"`, `"4"`) representa una empresa.
- La clave interna (`"1"`, `"2"`) representa un dominio (QA, CC, etc.).
- Los valores son hostnames o direcciones de servidor.

Las claves numéricas se mapean a nombres legibles mediante `ServerResolver`.

---

## `ServerResolver` y la UI

El servicio `ServerResolver` (`services/server_resolver.py`):

- Mantiene:
  - `_empresa_claves`: por ejemplo:
    - `"ITCO": "1"`, `"TRA": "2"`, `"REPS": "3"`, `"REPP": "4"`.
  - `_opciones_dominio`: por ejemplo:
    - `"QA": "1"`, `"CC": "2"`.
- Expone:
  - `empresa_claves_view()` y `opciones_dominio_view()`:
    - Diccionarios inmutables utilizados por la UI para llenar combos de empresa y dominio.
- Método clave:
  - `generar_server(empresa, dominio)`:
    - Traducen `empresa` + `dominio` a sus claves y consultan `servers.json`.
    - Devuelven el hostname a usar en `scripts/importar_all` y otros procesos.

---

## Uso en los pipelines

Siempre que se necesita un servidor remoto, los handlers suelen hacer:

- Obtener empresa y dominio desde la UI.
- Llamar a `app.generar_server(empresa, dominio)` (que delega en `ServerResolver`).
- Si se obtiene un hostname válido:
  - Se arma el comando de importación, por ejemplo:
    - `scripts.importar_all <hostname> <empresa> <modos> --usecase ...`.
- Si no:
  - Se registra un error (“no se pudo resolver servidor para la empresa/dominio seleccionados”).

Esto ocurre en:

- Actualización global de datos.
- Flujos de Buscar Keys, HSH, Jobs, Unifilares, etc.

---

## Impacto de modificar `servers.json`

Cambiar hostnames:

- Necesario cuando:
  - Cambia la infraestructura (nuevos servidores).
  - Se deprecan servidores antiguos.
- Debe hacerse con cuidado:
  - Asegurándose de que los nuevos servidores están accesibles.
  - Verificando que tienen los datos esperados.

Cambiar claves o estructura:

- Si se modifican las claves (por ejemplo, `"1"` ya no es ITCO):
  - Es obligatorio ajustar también `_empresa_claves` y `_opciones_dominio` en `ServerResolver`.
  - De lo contrario, la UI podría seguir mostrando empresas/dominios que no corresponden a los hostnames configurados.

---

## Buenas prácticas

- Mantener `servers.json` sincronizado con:
  - La realidad de la infraestructura.
  - La lógica de `SecurityService` y `ServerResolver`.
- Documentar cambios:
  - Quién cambió qué.
  - Cuándo y por qué.
  - Qué flujos se verán afectados.

Cuando se añaden nuevos entornos (por ejemplo, nuevos dominios), se debe:

- Extender también `_opciones_dominio` en `ServerResolver`.
- Revisar scripts y documentación para asegurar que los nuevos entornos se usan correctamente.

