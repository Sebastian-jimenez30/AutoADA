"""
Creador de vault cifrado con (username + password) usando PBKDF2-HMAC(SHA256) -> Fernet.
 
- Genera vault.bin en el cwd.
- Lee PEMs desde scripts/cifrar/ (mismo esquema que ya usas).
- Usa claves de configuración alineadas a AppController.secure_env:
    - mongo_user, mongo_pass, mongo_port, replica_set
    - ssh_user, ssh_key_pem, ssh_key_passphrase, ssh_port
    - sca_hosts, his_hosts
    - tls_cert_key_pem, tls_ca_cert
- Incluye alias legacy: ca_cert, cert_key_pem, ssh_key_password, cert_tls, key_tls
 
Necesitas: cryptography
"""
 
import os
import json
import base64
import getpass
from typing import Any, Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes  # type: ignore
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # type: ignore
 
# =========================
# AJUSTA ESTOS VALORES
# (o deja vacíos y rellena PEMs)
# =========================
MONGO_USER = "osiadmin"
MONGO_PASS = "GJgSHWxVHmYqbg"
MONGO_PORT = 27030
REPLICA_SET = "HSHMongo"
SSH_USER = "ada"
SSH_KEY_PASSPHRASE = "k&Bp2@F@daH#BX&C2m4W!!NtH"
SCA_HOSTS = ["itco1sca01", "itco1sca02"]
HIS_HOSTS = ["itco1his01", "itco1his02"]
SSH_PORT = 22

ODBC_DRIVER = "PostgreSQL Unicode"
ODBC_DB = "hist"
ODBC_USER = "osi"
ODBC_PASS = "KK3bUdz9"
ODBC_PORT = 5432

USER_PI = "osiserv_act"
PASS_PI = "sB-DV4x!"

# =========================
# Lectura de archivos PEM
# =========================
def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
 
def _pem_paths() -> Dict[str, str]:
    base_dir = os.path.join(os.path.dirname(__file__), "cifrar")
    return {
        "mongo_ca":     os.path.join(base_dir, "mongo_ca.pem"),
        "mongo_client": os.path.join(base_dir, "mongo_client.pem"),
        "ssh_key":      os.path.join(base_dir, "key-py.pem"),
    }
 
 
# =========================
# Derivación de clave (username + password)
# =========================
_APP_SALT_PREFIX = b"ADA-DOT|"
 
def _derive_key_from_username_password(username: str, password: str) -> bytes:
    if not username:
        raise ValueError("El username no puede estar vacío.")
    if not password:
        raise ValueError("El password no puede estar vacío.")
    salt = _APP_SALT_PREFIX + username.encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)
 
 
def main() -> None:
    print("=== Creador de vault (username + password) ===")
    username = input("👤 Ingrese el username para el vault: ").strip()
    password = input("🔐 Ingrese la clave maestra: ").strip()
    password2 = input("🔐 Confirme la clave maestra: ").strip()
    if password != password2:
        raise SystemExit("Las claves no coinciden.")
 
    key = _derive_key_from_username_password(username, password)
    f = Fernet(key)
 
    # Carga PEMs
    paths = _pem_paths()
    try:
        ca_cert_content       = _read_text(paths["mongo_ca"])
        cert_key_pem_content  = _read_text(paths["mongo_client"])
        ssh_key_pem_content   = _read_text(paths["ssh_key"])
    except FileNotFoundError as e:
        raise SystemExit(f"No se encontraron PEMs esperados en scripts/cifrar/: {e}")
 
    # Vault alineado + alias legacy por compatibilidad
    vault: Dict[str, Any] = {
        # --- Mongo ---
        "mongo_user": MONGO_USER,
        "mongo_pass": MONGO_PASS,
        "mongo_port": MONGO_PORT,
        "replica_set": REPLICA_SET,
 
        # --- SSH / túneles ---
        "ssh_user": SSH_USER,
        "ssh_key_pem": ssh_key_pem_content,
        "ssh_key_passphrase": SSH_KEY_PASSPHRASE,
        "ssh_port": SSH_PORT,
 
        # --- Hosts ---
        "sca_hosts": SCA_HOSTS,
        "his_hosts": HIS_HOSTS,
 
        # --- TLS certs (nombres que espera secure_env) ---
        "tls_cert_key_pem": cert_key_pem_content,
        "tls_ca_cert": ca_cert_content,
 
        # --- Aliases legacy (por si otros scripts viejos los leen) ---
        "ca_cert": ca_cert_content,
        "cert_key_pem": cert_key_pem_content,
        "ssh_key_password": SSH_KEY_PASSPHRASE,
        "cert_tls": cert_key_pem_content,
        "key_tls": ca_cert_content,

        # --- ODBC / PostgreSQL ---
        "odbc_driver": ODBC_DRIVER, 
        "odbc_db": ODBC_DB,
        "odbc_user": ODBC_USER,
        "odbc_pass": ODBC_PASS,
        "odbc_port": ODBC_PORT,

        # --- PI --- 
        "user_pi": USER_PI,
        "pass_pi": PASS_PI,
 
        # --- Campo libre para futuras configs ---
        "extra_config": {},
 
        # --- Metadatos útiles ---
        "_meta": {
            "username": username,
            "kdf": "PBKDF2HMAC(SHA256, iterations=200000, salt=ADA-DOT|<username>)",
            "format": "Fernet",
        },
    }
 
    encrypted = f.encrypt(json.dumps(vault).encode("utf-8"))
    out_path = os.path.join(os.getcwd(), "ITCO.bin")
    with open(out_path, "wb") as fh:
        fh.write(encrypted)
 
    print(f"✅ Vault generado con éxito: {out_path}")
    print("   - Esquema: username + password (PBKDF2 + Fernet)")
    print("   - Claves alineadas con AppController.secure_env")
    print("   - Incluye aliases legacy para compatibilidad")
 
 
if __name__ == "__main__":
    main()