# controllers/frame_router.py
from typing import Callable, Dict

class FrameRouter:
    def __init__(self, root):
        self.root = root
        self._registry: Dict[str, Callable[[], object]] = {}

    def register(self, key: str, factory: Callable[[], object]):
        self._registry[key] = factory

    def build(self, key: str):
        """
        Construye y retorna el frame, sin hacer pack/grid.
        AppController se encarga de montarlo.
        """
        factory = self._registry.get(key)
        if not factory:
            raise KeyError(f"Vista no registrada: {key}")
        return factory()
