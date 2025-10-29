import io
import os
import paramiko
from pymongo import MongoClient
from sshtunnel import SSHTunnelForwarder
import _Logger as Logger
 
def _get_env(name: str, default=None, required: bool = False):
    val = os.environ.get(name, default)
    if required and (val is None or val == ""):
        raise ValueError(f"Falta variable de entorno requerida: {name}")
    return val
 
def _load_ssh_key_from_env() -> paramiko.PKey:
    pem_str = _get_env("SSH_KEY_PEM", required=True)
    passphrase = _get_env("SSH_KEY_PASSPHRASE", default=None, required=False)
    stream = io.StringIO(pem_str)
    try:
        return paramiko.RSAKey.from_private_key(stream, password=passphrase)
    except Exception:
        stream.seek(0)
        try:
            return paramiko.Ed25519Key.from_private_key(stream, password=passphrase)
        except Exception:
            stream.seek(0)
            try:
                return paramiko.ECDSAKey.from_private_key(stream, password=passphrase)
            except Exception as e:
                raise ValueError(f"No se pudo cargar la clave privada SSH: {e}")
 
# =========================
# Conexion SSH 
# =========================
def sshserver(server: str, logger, logger_console) -> paramiko.SSHClient:
    ssh_user = _get_env("SSH_USER", required=True)
    ssh_port = int(_get_env("SSH_PORT", default="22"))
    pkey = _load_ssh_key_from_env()
    try:
        Logger.write_log().log_all('info', f'Inicia conexion SSH con {server}:{ssh_port}', logger_console, logger)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=server, port=ssh_port, username=ssh_user, pkey=pkey, look_for_keys=False)
        Logger.write_log().log_all('info', f'Conexion SSH establecida con {server}', logger_console, logger)
        return client
    except Exception as e:
        logger_console.exception(f'Fallo conectando a {server}', exc_info=False)
        logger.exception(e, exc_info=True)
 
# =========================
# Detectar SCADA online
# =========================
def scada_online(client: paramiko.SSHClient, logger=None, logger_console=None):
    stdin, stdout, stderr = client.exec_command('. ~/.bash_profile && dbstat 10')
    output = stdout.read().decode(errors="ignore")
    online_server = None
    for line in output.splitlines():
        if "Status: ONLINE" in line and "Source" in line:
            try:
                server_part = line.split(":")[1]
                online_server = server_part.split("Status")[0].strip()
                if logger:
                    Logger.write_log().log_all('info', f'Servidor en linea: {online_server}', logger_console, logger)
            except IndexError:
                pass
    return online_server
 
# =========================
# Conexion HSH (Mongo vía túnel SSH + TLS)
# =========================
def conexion_hsh(empresa: str, server: str, logger, logger_console):
    ssh_port = int(_get_env("SSH_PORT", default="22"))
    mongo_port = int(_get_env("MONGO_PORT", default="27017"))
    mongo_user = _get_env("MONGO_USER", required=True)
    mongo_pass = _get_env("MONGO_PASS", required=True)
    replica_set = _get_env("REPLICA_SET", required=True)
    tls_cert_key = _get_env("TLS_CERT_KEY_PEM", required=True)
    tls_ca_cert = _get_env("TLS_CA_CERT", required=True)
    ssh_user = _get_env("SSH_USER", required=True)
    pkey = _load_ssh_key_from_env()
 
    SERVER_PREFIX = next((server.split(p)[0] for p in ["sca", "qds"] if p in server), server)

    cert_path = os.path.abspath("tls_cert.pem")
    ca_path = os.path.abspath("tls_ca.pem")

    def _cleanup_temp_files():
        for temp in (cert_path, ca_path):
            if temp and os.path.exists(temp):
                try:
                    os.remove(temp)
                except Exception:
                    pass

    def _is_primary(client: MongoClient) -> bool:
        try:
            info = client.admin.command("hello")
        except Exception:
            try:
                info = client.admin.command("isMaster")
            except Exception:
                Logger.write_log().log_all(
                    'warning',
                    'No fue posible determinar el rol del nodo Mongo (hello/isMaster fallaron)',
                    logger_console,
                    logger,
                )
                return True

        Logger.write_log().log_all(
            'debug',
            f'Respuesta hello/isMaster: {info}',
            logger_console,
            logger,
        )
        is_primary = info.get("isWritablePrimary")
        if is_primary is None:
            is_primary = info.get("ismaster")
        if not is_primary:
            primary_name = info.get("primary") or info.get("me")
            Logger.write_log().log_all(
                'warning',
                f'El nodo reporta no ser primario. primary={primary_name}',
                logger_console,
                logger,
            )
        return bool(is_primary)

    def _write_tls_files():
        with open(cert_path, "w", encoding="utf-8") as f:
            f.write(tls_cert_key)
        with open(ca_path, "w", encoding="utf-8") as f:
            f.write(tls_ca_cert)
        try:
            os.chmod(cert_path, 0o600)
            os.chmod(ca_path, 0o600)
        except Exception:
            pass
 
    for sca_num in ["01", "02"]:
        for his_num in ["01", "02"]:
            ssh_host = f"{SERVER_PREFIX}sca{sca_num}"
            his_host = f"{SERVER_PREFIX}his{his_num}"
            Logger.write_log().log_all('info', f'Intentando conexion: SCA={ssh_host} -> HIS={his_host}', logger_console, logger)
            try:
                tunnel = SSHTunnelForwarder(
                    ssh_address_or_host=(ssh_host, ssh_port),
                    ssh_username=ssh_user,
                    ssh_pkey=pkey,
                    remote_bind_address=(his_host, mongo_port),
                    local_bind_address=("localhost", mongo_port),
                )
                tunnel.start()
                Logger.write_log().log_all('info', f'Tunel SSH activo con {ssh_host}', logger_console, logger)

                _write_tls_files()
                mongo_uri = (
                    f"mongodb://{mongo_user}:{mongo_pass}@localhost:{mongo_port}/"
                    f"?authSource=admin&replicaSet={replica_set}&directConnection=true&readPreference=primary"
                )

                # 🔍 DEBUG extra
                Logger.write_log().log_all('debug', f'Mongo URI: {mongo_uri}', logger_console, logger)
                Logger.write_log().log_all('debug', f'Certificados usados: cert={cert_path}, CA={ca_path}', logger_console, logger)

                client = MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=5000,
                    tls=True,
                    tlsCertificateKeyFile=cert_path,
                    tlsCAFile=ca_path,
                    tlsAllowInvalidHostnames=True,
                )

                try:
                    client.admin.command("ping")
                    Logger.write_log().log_all('info', f'Conexion MongoDB exitosa (HIS={his_host})', logger_console, logger)
                except Exception as e:
                    Logger.write_log().log_all('error', f'Ping a Mongo fallo: {e}', logger_console, logger)
                    raise

                if _is_primary(client):
                    Logger.write_log().log_all('info', f'HIS {his_host} es primario, listo para escribir', logger_console, logger)
                    try:
                        setattr(client, "_hsh_host", his_host)
                        setattr(client, "_ssh_host", ssh_host)
                    except Exception:
                        pass
                    return client, tunnel, cert_path, ca_path

                Logger.write_log().log_all('warning', f'HIS {his_host} no es primario, probando siguiente nodo', logger_console, logger)
                try:
                    client.close()
                except Exception:
                    pass
                try:
                    tunnel.stop()
                except Exception:
                    pass
                _cleanup_temp_files()
                continue

            except Exception as e:
                logger_console.exception(f'Fallo {ssh_host} -> {his_host}', exc_info=False)
                Logger.write_log().log_all('debug', f'Detalle error: {e}', logger_console, logger)
                try:
                    if 'tunnel' in locals() and tunnel.is_active:
                        tunnel.stop()
                except Exception:
                    pass
                _cleanup_temp_files()

    Logger.write_log().log_all('error', f'No se pudo conectar a ningun SCA/HIS para "{empresa}"', logger_console, logger)
    raise ConnectionError("Conexion Mongo por tunel fallida. Revisa credenciales, puertos y certificados.")
