# 00-04 – Mapa de la wiki

Esta página resume la estructura propuesta de la documentación. Algunas secciones pueden estar en construcción; este mapa sirve como guía de navegación y backlog de documentación.

> Nota: las rutas se asumen bajo `docs/wiki/`.

---

## 0. Portada y resumen del proyecto

- `00-Home.md` – Portada y guía inicial.
- `00-01-Resumen-ejecutivo.md` – Propósito, beneficios y vista de alto nivel.
- `00-02-Alcance-y-limitaciones.md` – Qué cubre y qué no cubre AutoADA.
- `00-03-Tecnologias-y-entorno.md` – Stack técnico, despliegue y datos.
- `00-04-Mapa-de-la-wiki.md` – Esta página.

---

## 1. Contexto de negocio y operativo

- `01-Contexto-Negocio/Index.md`
  - `01-Contexto-Negocio/01-01-Equipo-y-stakeholders.md`
  - `01-Contexto-Negocio/01-02-Procesos-que-automatiza.md`
  - `01-Contexto-Negocio/01-03-Flujos-antes-y-despues-de-AutoADA.md`
  - `01-Contexto-Negocio/01-04-Requisitos-funcionales-y-no-funcionales.md`

---

## 2. Arquitectura global

- `02-Arquitectura/Index.md`
  - `02-Arquitectura/02-01-Vista-de-capas.md`
  - `02-Arquitectura/02-02-Flujo-de-arranque-y-login.md`
  - `02-Arquitectura/02-03-Modelo-de-ejecucion-asincrona.md`
  - `02-Arquitectura/02-04-Gestion-de-rutas-y-entornos.md`
  - `02-Arquitectura/02-05-Vista-de-dependencias-externas.md`

---

## 3. Componentes de código (arquitectura interna)

- `03-Componentes-Codigo/Index.md`
  - `03-Componentes-Codigo/03-01-Entrypoint-y-dispatcher.md`
  - `03-Componentes-Codigo/03-02-Controllers-y-routing.md`
  - `03-Componentes-Codigo/03-03-Views-e-interfaces-Tkinter.md`
  - `03-Componentes-Codigo/03-04-Servicios-transversales.md`
  - `03-Componentes-Codigo/03-05-Utils-y-helpers.md`
  - `03-Componentes-Codigo/03-06-Scripts-CLI-principales.md`
  - `03-Componentes-Codigo/03-07-Plantillas-y-assets.md`
  - `03-Componentes-Codigo/03-08-Estado-y-modelos.md`

---

## 4. Flujos funcionales / Pipelines

- `04-Flujos-Funcionales/Index.md`
  - `04-Flujos-Funcionales/04-01-Actualizar-datos-global.md`
  - `04-Flujos-Funcionales/04-02-Buscar-Key-Keys.md`
  - `04-Flujos-Funcionales/04-03-HSH-Validacion-tags.md`
  - `04-Flujos-Funcionales/04-04-HSH-Creacion-Cambio-Eliminar-tags.md`
  - `04-Flujos-Funcionales/04-05-Jobs-Crear-senales.md`
  - `04-Flujos-Funcionales/04-06-Jobs-Eliminar-y-Cambiar-nombre.md`
  - `04-Flujos-Funcionales/04-07-Unifilares-Importar-y-Validar.md`
  - `04-Flujos-Funcionales/04-08-Pruebas-PyP-V1.md`
  - `04-Flujos-Funcionales/04-09-Pruebas-PyP-V2.md`
  - `04-Flujos-Funcionales/04-10-Consultar-RTU-SAS.md`

---

## 5. Manual de usuario (GUI)

- `05-Manual-Usuario/Index.md`
  - `05-Manual-Usuario/05-01-Conceptos-basicos-de-la-UI.md`
  - `05-Manual-Usuario/05-02-Pantalla-Bienvenida-y-Estado-de-datos.md`
  - `05-Manual-Usuario/05-03-Buscar-Key.md`
  - `05-Manual-Usuario/05-04-Buscar-Keys-desde-Excel.md`
  - `05-Manual-Usuario/05-05-HSH-Crear-Tag.md`
  - `05-Manual-Usuario/05-06-HSH-Validar-Tags-y-Cambios.md`
  - `05-Manual-Usuario/05-07-HSH-Eliminar-Tags.md`
  - `05-Manual-Usuario/05-08-Jobs-Crear-Eliminar-Cambiar-Nombre.md`
  - `05-Manual-Usuario/05-09-Unifilares.md`
  - `05-Manual-Usuario/05-10-Pruebas-PyP-V1.md`
  - `05-Manual-Usuario/05-11-Pruebas-PyP-V2.md`
  - `05-Manual-Usuario/05-12-Consultar-RTU-SAS.md`
  - `05-Manual-Usuario/05-13-Actualizar-datos-desde-Bienvenida.md`

---

## 6. Datos, configuración y perfiles

- `06-Datos-Configuracion/Index.md`
  - `06-Datos-Configuracion/06-01-Estructura-de-out-y-log.md`
  - `06-Datos-Configuracion/06-02-Config-import_profiles.md`
  - `06-Datos-Configuracion/06-03-Config-buscar_key-y-db_names.md`
  - `06-Datos-Configuracion/06-04-Diccionario-de-tags-y-plantillas-HSH.md`
  - `06-Datos-Configuracion/06-05-Config-servers-y-dominios.md`
  - `06-Datos-Configuracion/06-06-Plantillas-Excel.md`
  - `06-Datos-Configuracion/06-07-Convenciones-de-nombres-de-archivos-y-carpetas.md`

---

## 7. Seguridad, credenciales y accesos

- `07-Seguridad/Index.md`
  - `07-Seguridad/07-01-Modelo-de-seguridad-general.md`
  - `07-Seguridad/07-02-Vault-cifrado-y-esquemas-de-clave.md`
  - `07-Seguridad/07-03-Variables-de-entorno-cargadas.md`
  - `07-Seguridad/07-04-Restricciones-por-hostname-y-ubicacion.md`
  - `07-Seguridad/07-05-Certificados-TLS-SSH-y-archivos-cifrados.md`
  - `07-Seguridad/07-06-Buenas-practicas-para-manejo-de-credenciales.md`

---

## 8. Operación, soporte y mantenimiento

- `08-Operacion-Soporte/Index.md`
  - `08-Operacion-Soporte/08-01-Checklist-de-operacion-diaria.md`
  - `08-Operacion-Soporte/08-02-Como-verificar-que-los-datos-estan-actualizados.md`
  - `08-Operacion-Soporte/08-03-Lectura-y-gestion-de-logs.md`
  - `08-Operacion-Soporte/08-04-Limpieza-de-out-y-log.md`
  - `08-Operacion-Soporte/08-05-Resolucion-de-problemas-comunes.md`
  - `08-Operacion-Soporte/08-06-Procedimiento-para-reportar-incidentes.md`

---

## 9. Desarrollo, build y DevOps

- `09-Desarrollo-Build/Index.md`
  - `09-Desarrollo-Build/09-01-Guia-para-desarrolladores.md`
  - `09-Desarrollo-Build/09-02-Estructura-del-repo-y-convenciones-de-codigo.md`
  - `09-Desarrollo-Build/09-03-Proceso-de-build-con-PyInstaller.md`
  - `09-Desarrollo-Build/09-04-Pruebas-y-scripts-de-diagnostico.md`
  - `09-Desarrollo-Build/09-05-Agregar-nuevas-funcionalidades.md`
  - `09-Desarrollo-Build/09-06-Integracion-con-Azure-DevOps.md`

---

## 10. Anexos, glosario y referencias

- `10-Anexos/Index.md`
  - `10-Anexos/10-01-Glosario.md`
  - `10-Anexos/10-02-Tabla-de-dependencias-python.md`
  - `10-Anexos/10-03-Tabla-de-scripts-y-argumentos.md`
  - `10-Anexos/10-04-Mapa-completo-del-repositorio.md`
  - `10-Anexos/10-05-Referencias-externas.md`

---

## Uso de este mapa

- Sirve como **índice global** de la wiki.
- Puede usarse como **lista de tareas de documentación**: secciones sin contenido se consideran pendientes.
- A medida que se consoliden las páginas, se pueden añadir enlaces internos, capturas de pantalla y diagramas a cada una.

