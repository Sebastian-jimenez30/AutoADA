# 02-03 – Modelo de ejecución asíncrona

AutoADA ejecuta procesos pesados (importar, convertir, validar, generar reportes) como **subprocesos** externos para no bloquear la interfaz Tkinter. Esta página explica cómo está diseñado ese modelo.

---

## Objetivos del modelo asíncrono

- Mantener la UI **responsiva** mientras corren scripts intensivos.
- Permitir que la usuaria/o:
  - Vea el avance detallado en una consola embebida.
  - Reciba feedback en la barra de estado.
  - Sepa claramente cuándo un proceso terminó o falló.
- Evitar que varios procesos compitan por los mismos recursos (por ejemplo, datos de una empresa) sin coordinación.

---

## Componente central: `TaskRunner`

Archivo: `utils/task_runner.py`.

Responsabilidades:

- Ejecutar comandos (`cmd: List[str]`) como subprocesos usando `subprocess.Popen`.
- Capturar stdout (y stderr redirigido a stdout) **línea a línea**.
- Encolar líneas de salida en un `queue.Queue`.
- Programar llamadas periódicas a un “bombeo” (`_pump`) usando `root.after(...)`:
  - Desencola líneas.
  - Llama a `on_progress(line)` (cuando se define).
  - Opcionalmente, escribe en un archivo de log.
- Detectar cuándo el proceso termina:
  - Llama a `on_done(returncode)` en el hilo de Tk mediante `root.after`.
  - Libera los locks asociados al recurso.

Adicionalmente:

- Mantiene un mapa `_running` de procesos activos (PID → info).
- Permite registrar listeners de estado (`add_state_listener`) para notificar cuándo hay tareas en ejecución.
- Implementa `stop_all()` para pedir terminación de procesos activos, con un “force kill” programado después de un tiempo.

---

## Serialización por recurso (`resource_key`)

`TaskRunner.run_subprocess` recibe un parámetro opcional `resource_key`.

- Si se pasa una `resource_key`:
  - TaskRunner garantiza que **no** se ejecuten dos procesos en paralelo con la misma clave.
  - Si ya hay uno corriendo, reprograma el intento (retry) después de un breve período (`root.after`).
- Esto se usa, por ejemplo, para evitar:
  - Dos importaciones simultáneas para la misma empresa.
  - Dos validaciones que necesitasen los mismos archivos intermedios.

Es una forma simple de control de concurrencia a nivel de aplicación.

---

## Integración con la UI (consola y status bar)

Los handlers (por ejemplo, `handlers/buscar_key`, `handlers/hsh`, `handlers/jobs`, etc.) pasan callbacks a `TaskRunner.run_subprocess`:

- `on_progress(line)`:
  - Limpia o formatea la línea.
  - Determina el nivel (info/warn/error) según palabras clave.
  - Escribe en `LogConsole` (texto embebido en la vista).
  - Puede actualizar la barra de estado (por ejemplo, con el prefijo de etapa: `[IMPORT]`, `[CONVERT]`, `[SCAN]`, etc.).
- `on_done(returncode)`:
  - Reacciona al código de retorno:
    - `0`: éxito → diálogos de éxito, reactivación de botones, actualización de etiquetas.
    - distinto de `0`: error → mensajes de error, mantener console output para diagnóstico.

`AppController` se suscribe a los cambios de estado del `TaskRunner`:

- En `_on_task_runner_state(running: bool)`:
  - Si hay tareas corriendo y no hay un estado manual (forzado por handler):
    - Activa la barra de progreso en modo indeterminado (`statusbar.start(...)`).
  - Cuando no quedan tareas:
    - Marca “Listo” en la barra de estado (salvo que se haya establecido un estado manual).
  - Ajusta el botón Detener de la consola (`LogConsole.set_stop_enabled`).

De esta forma, la usuaria/o tiene feedback inmediato sin ver detalles del modelo asíncrono interno.

---

## Botón “Detener” y cancelación

La consola (`LogConsole`) integra un botón “Detener” que:

- Llama a `AppController.stop_running_tasks()`.
- Este método invoca `TaskRunner.stop_all()`:
  - Para cada proceso activo:
    - Intenta enviar `terminate()`.
    - Escribe un mensaje en la consola (`[runner] stop requested`).
  - Programa una llamada posterior a `_force_kill()`:
    - Intenta `kill()` los procesos que sigan vivos tras el tiempo de gracia.

Limitaciones:

- No todos los scripts pueden interrumpirse de forma limpia (depende de lo que hagan internamente).
- Aun así, este mecanismo ofrece una salida controlada para evitar que procesos se queden colgados indefinidamente.

---

## Relaciones con scripts CLI

Desde el punto de vista de `TaskRunner`:

- Los scripts CLI son **cajas negras** que leen variables de entorno y archivos, y escriben en stdout.
- Se recomienda que los scripts:
  - Emitan mensajes estructurados (prefijos, rutas de salida en líneas claras).
  - Usen códigos de retorno distintos de cero para indicar errores.
  - No bloqueen indefinidamente sin output.

Handlers como `handlers.consultar.rtu`, `handlers.actualizar_datos` y los de HSH/Jobs/Unifilares parsan ciertas líneas especiales (por ejemplo, rutas de archivos generados) para presentarlas en diálogos de éxito.

---

## Beneficios del modelo actual

- Mantiene la **interfaz fluida** aun en procesos largos.
- Permite un **log detallado en tiempo real** en la propia aplicación.
- Evita la sobrecarga de hilos de negocio en la lógica Tkinter, delegando el trabajo pesado a subprocesos.
- Ofrece un punto único para:
  - Manejo de errores de subprocesos.
  - Registro a archivo.
  - Política de cancelación.

Este modelo es un pilar clave de la arquitectura de AutoADA, ya que la mayoría de funcionalidades dependen de scripts intensivos.

