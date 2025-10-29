"""
Manejo del vault encriptado (Fernet) para cargar secretos en memoria.
 
NUEVO:
- Soporta credenciales (username + password) para derivar la clave del vault.
- Mantiene compatibilidad con el esquema anterior (sólo password).
  -> Intentará primero con (username+password). Si falla, intenta legacy (sólo password).
 
Ubicaciones esperadas del vault:
- onefile: <bundle_root>/vault/vault.bin  (al empaquetar con --add-data "scripts\\vault.bin;vault")
- dev:     scripts/vault.bin               (junto a este archivo)
 
API:
- load_vault_from_credentials(username, password, ...)
- load_vault_from_password(password, ...)             # DEPRECATED: mantiene compatibilidad con código existente
"""
 
from __future__ import annotations
 
import base64
import json
import os
import sys
from typing import Any, Dict, Iterable, Optional
 
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes  # type: ignore
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # type: ignore
 
 
# -------------------------
# Paths helpers (onefile)
# -------------------------
 
def _bundle_root() -> str:
    """Raíz de recursos de solo lectura:
    - onefile: sys._MEIPASS
    - dev: carpeta de este archivo
    """
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))
 
 
def _resolve_default_vault_path() -> str:
    """Prioridad:
    1) <bundle_root>/vault/vault.bin
    2) <este_directorio>/vault.bin
    Lanza FileNotFoundError si no existe.
    """
    candidate1 = os.path.join(_bundle_root(), "vault", "vault.bin")
    if os.path.exists(candidate1):
        return candidate1
    candidate2 = os.path.join(os.path.dirname(__file__), "vault.bin")
    if os.path.exists(candidate2):
        return candidate2
    raise FileNotFoundError(
        "No se encontró 'vault.bin'. Esperado en 'vault/vault.bin' dentro del bundle "
        "o junto a este archivo en desarrollo (scripts/vault.bin)."
    )


def resolve_named_vault_path(filename: str) -> str:
    """Busca un vault específico siguiendo las mismas reglas que el default."""
    if not filename:
        raise ValueError("Nombre de vault inválido")
    candidate1 = os.path.join(_bundle_root(), "vault", filename)
    if os.path.exists(candidate1):
        return candidate1
    candidate2 = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(candidate2):
        return candidate2
    raise FileNotFoundError(
        f"No se encontró '{filename}'. Esperado en 'vault/{filename}' dentro del bundle "
        f"o junto a este archivo en desarrollo (scripts/{filename})."
    )


# -------------------------
# Key derivation
# -------------------------

_APP_SALT_PREFIX = b"ADA-DOT|"  
 
def _derive_key_from_username_password(username: str, password: str) -> bytes:
    """Deriva una clave de 32 bytes (Fernet) usando PBKDF2-HMAC(SHA256),
    con salt = APP_SALT_PREFIX + username.
 
    Iteraciones: 200k (ajusta si necesitas más/menos costo).
    Devuelve la clave en formato urlsafe_b64 (requerido por Fernet).
    """
    if not isinstance(username, str) or not username:
        raise ValueError("username requerido para derivación con PBKDF2.")
    if not isinstance(password, str) or not password:
        raise ValueError("password requerido para derivación con PBKDF2.")
 
    salt = _APP_SALT_PREFIX + username.encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)
 
 
def _legacy_key_from_password(password: str) -> bytes:
    """Esquema LEGACY (compatibilidad): padding/truncado a 32 y urlsafe_b64encode."""
    return base64.urlsafe_b64encode(password.ljust(32)[:32].encode("utf-8"))
 
 
# -------------------------
# Carga / Desencriptado
# -------------------------
 
def _load_and_decrypt(path: str, key: bytes) -> Dict[str, Any]:
    fernet = Fernet(key)
    with open(path, "rb") as fh:
        encrypted = fh.read()
    decrypted = fernet.decrypt(encrypted)
    vault = json.loads(decrypted)
    if not isinstance(vault, dict):
        raise ValueError("El contenido del vault no es un objeto JSON.")
    return vault
 
 
def load_vault_from_credentials(
    username: str,
    password: str,
    vault_path: Optional[str] = None,
    require_authorized: bool = False,  # ignorado (compatibilidad)
    required_keys: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Desencripta 'vault.bin' usando (username + password). Si falla, intenta
    con el esquema legacy (sólo password).
 
    Args:
      username: Usuario para la derivación de clave (nuevo esquema).
      password: Contraseña maestra.
      vault_path: Ruta explícita al vault (opcional). Si no se indica:
        - <bundle_root>/vault/vault.bin  (onefile)
        - scripts/vault.bin              (dev)
      require_authorized: Ignorado (compatibilidad).
      required_keys: Claves mínimas requeridas; lanza ValueError si falta alguna.
 
    Returns:
      Dict con secretos.
    """
    path = vault_path or _resolve_default_vault_path()
 
    # 1) Intento con esquema nuevo (username + password)
    try:
        key = _derive_key_from_username_password(username, password)
        vault = _load_and_decrypt(path, key)
    except FileNotFoundError:
        raise
    except Exception as e_new:
        # 2) Fallback a LEGACY (sólo password)
        try:
            key_legacy = _legacy_key_from_password(password)
            vault = _load_and_decrypt(path, key_legacy)
        except Exception as e_legacy:
            # Reporta error claro incluyendo ambos intentos
            raise ValueError(
                f"Clave incorrecta o vault corrupto. "
            )
 
    # Validación de claves requeridas
    if required_keys:
        faltan = [k for k in required_keys if k not in vault]
        if faltan:
            raise ValueError(f"Vault inválido: faltan claves requeridas: {', '.join(faltan)}")
 
    return vault
 
