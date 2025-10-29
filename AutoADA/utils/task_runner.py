# utils/task_runner.py
# -*- coding: utf-8 -*-
import subprocess
import threading
import queue
from typing import Any, Callable, Dict, List, Optional


class TaskRunner:
    """
    Ejecuta subprocesos sin bloquear la UI de Tkinter.
    - Captura stdout + stderr (unidos) en tiempo real y los pasa a on_progress(line).
    - Llama a on_done(returncode) al finalizar SIEMPRE.
    - Serializa por resource_key (locks simples).
    """

    def __init__(self, tk_root, log_path: Optional[str] = None):
        self.root = tk_root
        self._locks: Dict[str, bool] = {}
        self._log_path = log_path
        self._running: Dict[int, Dict[str, Any]] = {}
        self._listeners: List[Callable[[bool], None]] = []

    def run_subprocess(
        self,
        cmd: List[str],
        resource_key: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
        on_done: Optional[Callable[[int], None]] = None,
    ):
        # Serialización por recurso
        if resource_key:
            if self._locks.get(resource_key, False):
                def _retry():
                    self.run_subprocess(cmd, resource_key, env, cwd, on_progress, on_done)
                self.root.after(400, _retry)
                return
            self._locks[resource_key] = True

        line_q: "queue.Queue[str]" = queue.Queue()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
                bufsize=1,                     # line-buffered
                env=env,
                cwd=cwd or None,
                shell=False,
                encoding="utf-8",              # asegura decodificación estable
                errors="replace",
            )
            # Línea de arranque para confirmar que el progress llega
            if on_progress:
                on_progress(f"[runner] started PID={proc.pid} CMD={' '.join(map(str, cmd))}")
            self._running[proc.pid] = {
                "process": proc,
                "on_progress": on_progress,
                "resource_key": resource_key,
            }
            self._notify_state_async()
        except Exception as e:
            if resource_key:
                self._locks[resource_key] = False
            if on_progress:
                on_progress(f"[runner] No se pudo iniciar el subproceso: {e}")
            if on_done:
                on_done(1)
            return

        def _reader():
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    line_q.put(line.rstrip("\r\n"))
            except Exception:
                pass
            finally:
                try:
                    if proc.stdout:
                        proc.stdout.close()
                except Exception:
                    pass

        def _pump():
            drained = False
            while True:
                try:
                    line = line_q.get_nowait()
                except queue.Empty:
                    break
                drained = True
                if on_progress:
                    try:
                        on_progress(line)
                    except Exception:
                        pass
                if self._log_path:
                    try:
                        with open(self._log_path, "a", encoding="utf-8") as f:
                            f.write(line + "\n")
                    except Exception:
                        pass

            # IMPORTANTE:
            # Reprogramar si el proceso sigue vivo O si aún quedan líneas en cola.
            if (proc.poll() is None) or (not line_q.empty()):
                self.root.after(80, _pump)

        # Hilo lector (mete líneas a la cola)
        t_out = threading.Thread(target=_reader, daemon=True)
        t_out.start()

        # Arranca el bombeo hacia la UI
        self.root.after(80, _pump)

        def _waiter():
            rc = proc.wait()
            try:
                t_out.join(timeout=1.0)
            except Exception:
                pass
            self._running.pop(proc.pid, None)
            if resource_key:
                self._locks[resource_key] = False
            # IMPORTANTE: hacer un último _pump por si quedaron líneas residuales
            self.root.after(0, _pump)
            self._notify_state_async()
            if on_done:
                self.root.after(0, lambda: on_done(rc))

        threading.Thread(target=_waiter, daemon=True).start()

    def add_state_listener(self, listener: Callable[[bool], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def is_running(self) -> bool:
        for info in list(self._running.values()):
            proc = info.get("process")
            if proc is not None and proc.poll() is None:
                return True
        return False

    def stop_all(self) -> bool:
        stopped = False
        for pid, info in list(self._running.items()):
            proc = info.get("process")
            if proc is None or proc.poll() is not None:
                continue
            stopped = True
            on_progress = info.get("on_progress")
            if callable(on_progress):
                try:
                    on_progress(f"[runner] stop requested PID={pid}")
                except Exception:
                    pass
            try:
                proc.terminate()
            except Exception:
                pass
        if stopped:
            self.root.after(2000, self._force_kill)
        else:
            self._notify_state_async()
        return stopped

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _force_kill(self) -> None:
        for info in list(self._running.values()):
            proc = info.get("process")
            if proc is None or proc.poll() is not None:
                continue
            try:
                proc.kill()
            except Exception:
                pass
        self._notify_state_async()

    def _notify_state_async(self) -> None:
        self.root.after(0, self._notify_state)

    def _notify_state(self) -> None:
        running = self.is_running()
        for listener in list(self._listeners):
            try:
                listener(running)
            except Exception:
                pass
