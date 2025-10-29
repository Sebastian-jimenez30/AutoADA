#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para conexión MongoDB por túnel SSH y exportación de colecciones a JSON.
Ajusta los valores de 'server' y 'empresa' según tu entorno de pruebas.
"""
import os
import sys
from functions import conexion_hsh
import logging
from bson import json_util
import pymongo

from vault_manager import load_vault
import getpass



# Configura aquí los valores de prueba
server = 'itco1'  # Ejemplo: 'rep1-app-01'
empresa = 'ITCO'           # Ejemplo: 'ITCO', 'REPS', 'REPP', 'TRA'

# Solicitar clave para abrir el vault
vault_password = getpass.getpass('Clave para abrir el vault: ')
vault = load_vault(vault_password)
mongo_user = vault['mongo_user']
mongo_pass = vault['mongo_pass']

# Logger básico para pruebas
class DummyLogger:
    def info(self, msg):
        print(f"[INFO] {msg}")
    def error(self, msg):
        print(f"[ERROR] {msg}")
    def warning(self, msg):
        print(f"[WARNING] {msg}")
    def debug(self, msg):
        print(f"[DEBUG] {msg}")
    def exception(self, msg, exc_info=True):
        print(f"[EXCEPTION] {msg}")

logger = DummyLogger()
logger_console = DummyLogger()

# Selección de base de datos según empresa
db_map = {
    'REPS': 'PI_REPS',
    'REPP': 'PI_REPP',
    'ITCO': 'PI_ITCO',
    'TRA':  'PI_TRA',
}
COLLECTIONS = ['groups', 'lookup_tables']

folder_name_output = f"test_export_{empresa}"
os.makedirs(folder_name_output, exist_ok=True)

try:
    print(f"Iniciando túnel SSH y conexión MongoDB para {empresa} en {server}...")
    client, tunnel, cert_path, key_path = conexion_hsh(empresa, server, logger, logger_console)
    print(f"cert_path: {cert_path}")
    print(f"key_path: {key_path}")
    # Usar la ruta absoluta del CA
    ca_path = '/opt/osi/monarch/sys/rc/ssl/ca-chain.cert.pem'
    print(f"ca_path: {ca_path}")
    # Imprimir primeros bytes de los archivos para verificar contenido
    def print_file_head(path, label):
        try:
            with open(path, 'r') as f:
                print(f"--- {label} ({path}) ---")
                for i in range(5):
                    line = f.readline()
                    if not line:
                        break
                    print(line.strip())
                print(f"--- Fin {label} ---\n")
        except Exception as e:
            print(f"No se pudo leer {label} ({path}): {e}")
    print_file_head(cert_path, 'Certificado')
    print_file_head(key_path, 'Key')
    print_file_head(ca_path, 'CA')
    try:
        mongo_client = pymongo.MongoClient(
            'localhost',
            27030,
            username=mongo_user,
            password=mongo_pass,
            authSource='admin',
            tls=True,
            tlsCAFile=ca_path,
            tlsCertificateKeyFile=cert_path
        )
        db = mongo_client[db_map[empresa]]
        print(f"Conexión exitosa a MongoDB. Exportando colecciones...")
        for name in COLLECTIONS:
            query = {"table_name": "Tabla1"} if name == "lookup_tables" else {}
            path = os.path.join(folder_name_output, f"{name}.json")
            count = db[name].count_documents(query)
            print(f"Colección '{name}': {count} documentos con el filtro {query}")
            if count == 0:
                print(f"'{name}' está vacía con el filtro aplicado.")
                continue
            with open(path, "w", encoding="utf-8") as f:
                for doc in db[name].find(query):
                    f.write(json_util.dumps(doc, ensure_ascii=False) + "\n")
            print(f"Exportado {name}.json ({count} documentos)")
        print(f"Exportación finalizada. Archivos en: {folder_name_output}")
    except Exception as e:
        print(f"Primer intento falló: {e}")
        print("Reintentando conexión sin validar certificado...")
        mongo_client = pymongo.MongoClient(
            'localhost',
            27030,
            username=mongo_user,
            password=mongo_pass,
            authSource='admin',
            tls=True,
            tlsAllowInvalidCertificates=True
        )
        db = mongo_client[db_map[empresa]]
        print(f"Conexión (sin validar certificado) exitosa a MongoDB. Exportando colecciones...")
        for name in COLLECTIONS:
            query = {"table_name": "Tabla1"} if name == "lookup_tables" else {}
            path = os.path.join(folder_name_output, f"{name}.json")
            count = db[name].count_documents(query)
            print(f"Colección '{name}': {count} documentos con el filtro {query}")
            if count == 0:
                print(f"'{name}' está vacía con el filtro aplicado.")
                continue
            with open(path, "w", encoding="utf-8") as f:
                for doc in db[name].find(query):
                    f.write(json_util.dumps(doc, ensure_ascii=False) + "\n")
            print(f"Exportado {name}.json ({count} documentos)")
        print(f"Exportación finalizada. Archivos en: {folder_name_output}")
    finally:
        tunnel.stop()
        if cert_path and os.path.exists(cert_path):
            os.remove(cert_path)
        if key_path and os.path.exists(key_path):
            os.remove(key_path)
except Exception as e:
    print(f"ERROR durante la exportación: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
