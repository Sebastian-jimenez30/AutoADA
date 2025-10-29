import threading
from typing import Callable, Any

def run_in_thread(fn: Callable[..., Any], on_finally: Callable[[], None] | None = None, *args, **kwargs):
    def _wrap():
        try:
            fn(*args, **kwargs)
        finally:
            if on_finally:
                on_finally()
    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    return t