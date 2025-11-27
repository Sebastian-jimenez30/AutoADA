# 07 – Seguridad, credenciales y accesos

Esta sección describe cómo AutoADA maneja **seguridad, credenciales y accesos**:

- Qué modelo de seguridad aplica (quién puede usar qué, y dónde).
- Cómo se gestionan vaults cifrados.
- Qué variables de entorno se cargan para scripts.
- Cómo se usan certificados TLS/SSH.
- Buenas prácticas para operar sin exponer información sensible.

---

## Contenido de esta sección

- `07-01-Modelo-de-seguridad-general.md`  
  Visión general de la seguridad en AutoADA y sus capas (UI, servicios, scripts).

- `07-02-Vault-cifrado-y-esquemas-de-clave.md`  
  Cómo funcionan los vaults encriptados, cómo se derivan las claves y cómo se resuelven.

- `07-03-Variables-de-entorno-cargadas.md`  
  Qué variables de entorno se inyectan desde el vault y cómo las usan los scripts.

- `07-04-Restricciones-por-hostname-y-ubicacion.md`  
  Cómo se determina si un equipo está autorizado (ITCO, REP, Desconocido) y qué implica.

- `07-05-Certificados-TLS-SSH-y-archivos-cifrados.md`  
  Uso de certificados TLS/SSH y archivos cifrados asociados a conexiones seguras.

- `07-06-Buenas-practicas-para-manejo-de-credenciales.md`  
  Recomendaciones operativas para proteger credenciales, vaults y resultados sensibles.

