from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AppState:
    usuario: Optional[str] = None
    rol: Optional[str] = None
    ubicacion: str = "Desconocido"
    empresa_activa: Optional[str] = None
    dominio_activo: Optional[str] = None