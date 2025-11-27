# 07-06 – Buenas prácticas para manejo de credenciales

Esta página recoge recomendaciones prácticas para usar AutoADA sin comprometer credenciales ni información sensible.

---

## 1. Gestión del vault

- Tratar los archivos de vault (`ITCO.bin`, `REPS.bin`, etc.) como **material sensible**:
  - No compartirlos por correo sin cifrado.
  - No copiarlos a dispositivos no controlados.
  - No subirlos a repositorios no autorizados.

- Cambiar el vault cuando:
  - Se cambien credenciales de sistemas externos.
  - Se sospeche de un posible compromiso.

- Mantener un registro interno de:
  - Cuándo se generó cada vault.
  - Qué credenciales contiene.
  - Qué usuarios/roles tienen acceso a él.

---

## 2. Uso del login

- No reutilizar el mismo password del vault como contraseña de otros sistemas personales.
- No compartir usuario/clave de vault:
  - Cada persona debe tener sus propias credenciales, si así lo define la política interna.

- Evitar:
  - Escribir el password en lugares visibles (post-its, documentos sin cifrar).

---

## 3. Variables de entorno y logs

- Asumir que las variables de entorno podrían ser visibles para:
  - Procesos del mismo usuario en el sistema.
  - Herramientas de depuración.

- Evitar que scripts:
  - Escriban en logs valores de:
    - `MONGO_PASS`, `ODBC_PASS`, `PASS_PI`, etc.
    - Cadenas que contengan llaves privadas o certificados completos.

- Revisar periódicamente:
  - Que los logs no contengan información sensible.
  - Ajustar scripts si se detecta filtración.

---

## 4. Archivos de salida y compartición

- Los archivos de salida (`out/`) pueden contener:
  - Nombres de tags.
  - Datos de configuración de señales.
  - Resultados de pruebas.

- Antes de compartir un archivo:
  - Verificar que su distribución es compatible con las políticas de confidencialidad.
  - Enmascarar o limpiar información sensible si se va a compartir fuera del equipo.

- Al archivar reportes:
  - Seguir las políticas de retención definidas por la organización.
  - Evitar guardar copias en ubicaciones personales sin respaldo corporativo.

---

## 5. Equipos y ubicaciones

- Asegurarse de usar AutoADA solo en:
  - Equipos autorizados por DOT/Intercolombia.
  - Entornos donde el hostname y la ubicación sean acordes a la configuración de `SecurityService`.

- Evitar:
  - Instalar/usar AutoADA en equipos personales no administrados.
  - Copiar el ejecutable y vaults a equipos fuera del ámbito previsto.

---

## 6. Cambios en configuración de seguridad

- Cualquier modificación en:
  - `SecurityService` (reglas de hostname).
  - `ServerResolver` (servidores).
  - Vaults.
  - Certificados (`*.pem`).
  debe:
  - Ser revisada por responsables técnicos y, si aplica, de seguridad.
  - Probarse en entornos no productivos antes de desplegarse ampliamente.

---

## 7. Educación y comunicación

- Asegurar que usuarias/os:
  - Entienden qué es el vault.
  - Saben que no deben manipular credenciales directamente.
  - Reconocen la importancia de no compartir archivos sensibles sin control.

- Documentar:
  - Procedimientos de recuperación ante pérdida de vault.
  - Contactos de soporte en caso de incidentes de seguridad.

Seguir estas prácticas ayuda a que AutoADA siga siendo una herramienta útil sin introducir riesgos adicionales para la seguridad de la información.

