import sys, os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOADA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AutoADA"))
if AUTOADA_DIR not in sys.path:
    sys.path.insert(0, AUTOADA_DIR)

from scripts.vault_manager import load_vault_from_credentials, resolve_named_vault_path
from services.security_service import SecurityService

class VaultService:
    _vault_data = None  # cache en memoria

    @classmethod
    def load_vault(cls, usuario: str, clave: str):
        """Desencripta el vault y lo guarda en memoria."""
        security = SecurityService()
        ubicacion = security.detectar_ubicacion()
        vault_filename = security.resolve_vault_filename(ubicacion)
        vault_path = None

        if vault_filename:
            try:
                vault_path = resolve_named_vault_path(vault_filename)
            except FileNotFoundError:
                vault_path = None

        vault = load_vault_from_credentials(usuario, clave, vault_path=vault_path)
        cls._vault_data = vault
        return vault

    @classmethod
    def build_env(cls) -> dict:
        """Convierte el vault desencriptado en un diccionario de entorno."""
        if not cls._vault_data:
            raise RuntimeError("Vault no cargado. Debes iniciar sesión primero.")

        vault = cls._vault_data
        env = os.environ.copy()
        loaded = []

        def set_env(k, v):
            if v is not None:
                env[k] = str(v)
                loaded.append(k)

        # SSH
        set_env("SSH_USER", vault.get("ssh_user"))
        set_env("SSH_KEY_PEM", vault.get("ssh_key_pem"))
        set_env("SSH_KEY_PASSPHRASE", vault.get("ssh_key_passphrase"))
        set_env("SSH_PORT", vault.get("ssh_port"))

        # Mongo
        set_env("MONGO_USER", vault.get("mongo_user"))
        set_env("MONGO_PASS", vault.get("mongo_pass"))
        set_env("MONGO_PORT", vault.get("mongo_port"))
        set_env("REPLICA_SET", vault.get("replica_set"))
        set_env("TLS_CERT_KEY_PEM", vault.get("tls_cert_key_pem"))
        set_env("TLS_CA_CERT", vault.get("tls_ca_cert"))

        # ODBC
        set_env("ODBC_USER", vault.get("odbc_user"))
        set_env("ODBC_PASS", vault.get("odbc_pass"))
        set_env("ODBC_DB", vault.get("odbc_db"))
        set_env("ODBC_DRIVER", vault.get("odbc_driver"))
        set_env("ODBC_PORT", vault.get("odbc_port") or "5432")

        # PI
        set_env("USER_PI", vault.get("user_pi"))
        set_env("PASS_PI", vault.get("pass_pi"))

        print(f"[WEB] Variables cargadas desde vault: {', '.join(loaded)}")
        return env
