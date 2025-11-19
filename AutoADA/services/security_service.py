import socket
from typing import Literal, Optional

Ubicacion = Literal["ITCO", "REP", "Desconocido"]


_VAULT_BY_UBICACION: dict[Ubicacion, str] = {
    "ITCO": "ITCO.bin",
    "REP": "REPS.bin",
}

class SecurityService:
    def detectar_ubicacion(self) -> Ubicacion:
        try:
            hostname = socket.gethostname().lower()
            if hostname.startswith(("itco1", "tra1", "isa1cct5_p", "desktop-n14qm43", "isa1ccwx_p")):
                return "ITCO"
            if hostname.startswith(("rep1", "rep2")):
                return "REP"
            return "Desconocido"
        except Exception:
            return "Desconocido"

    def resolve_vault_filename(self, ubicacion: Optional[Ubicacion] = None) -> Optional[str]:
        """Devuelve el nombre de archivo de vault sugerido según la ubicación detectada."""
        ubicacion = ubicacion or self.detectar_ubicacion()
        return _VAULT_BY_UBICACION.get(ubicacion)

    def empresas_permitidas(self, ubicacion: Ubicacion) -> list[str]:
        if ubicacion == "ITCO": return ["ITCO","TRA"]
        if ubicacion == "REP":  return ["REPS","REPP"]
        return ["ITCO","TRA","REPS","REPP"]

    def empresas_para_jobs(self, ubicacion: Ubicacion) -> list[str]:
        return ["ITCO"] if ubicacion == "ITCO" else (["REPS"] if ubicacion == "REP" else ["ITCO"])
