import json, os, sys
from typing import Optional, Mapping
from types import MappingProxyType

def get_resource_path(relative_path):
    """Obtiene la ruta correcta del recurso en ejecutable y desarrollo"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ServerResolver:
    def __init__(self, config_dir: str):
        # Usar get_resource_path para encontrar el archivo en el ejecutable
        self._path = get_resource_path("config/servers.json")
        self._empresa_claves = {"ITCO": "1", "TRA": "2", "REPS": "3", "REPP": "4"}
        self._opciones_dominio = {"QA": "1", "CC": "2"}

    # --- Vistas de solo lectura para la UI (evita duplicación en AppController) ---
    def empresa_claves_view(self) -> Mapping[str, str]:
        return MappingProxyType(self._empresa_claves)

    def opciones_dominio_view(self) -> Mapping[str, str]:
        return MappingProxyType(self._opciones_dominio)

    def generar_server(self, empresa: str, dominio: str) -> Optional[str]:
        ce = self._empresa_claves.get(empresa)
        cd = self._opciones_dominio.get(dominio)
        if not (ce and cd):
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                servers = json.load(f)
            return servers.get(ce, {}).get(cd)
        except FileNotFoundError:
            return None