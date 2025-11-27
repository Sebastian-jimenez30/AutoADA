from __future__ import annotations
import argparse
import os
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple, NamedTuple
import pandas as pd
from bson import Int64
from pymongo.errors import BulkWriteError

try:
    from scripts import _Logger as Logger  # type: ignore
    from scripts.hsh_crear_tag import (
        LOOKUP_TABLE_NAME, _candidate_base_dirs, _load_scada_data, _norm_key,
        _read_csv_lenient, _target_db, _read_scada_side, _primera_causa_desc,
        _related_company, _company_server_candidates, _related_servers
    )
    from scripts.hsh_eliminar_tag import _write_commands  # type: ignore
    from scripts.functions import conexion_hsh, sshserver  # type: ignore
except Exception:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
    import _Logger as Logger  # type: ignore
    from hsh_crear_tag import (
        LOOKUP_TABLE_NAME, _candidate_base_dirs, _load_scada_data, _norm_key,
        _read_csv_lenient, _target_db, _read_scada_side, _primera_causa_desc,
        _related_company, _company_server_candidates, _related_servers
    )  # type: ignore
    from hsh_eliminar_tag import _write_commands  # type: ignore
    from functions import conexion_hsh, sshserver  # type: ignore

from utils.paths import output_root

Pair = Tuple[str, str]
# === Sistema de Estado (mejorado) ===
verification_status: Dict[str, Dict[str, Dict[str, object]]] = {}
verification_order: List[str] = []

def _record_status(empresa: str, step: str, ok: Optional[bool] = None, message: Optional[str] = None) -> None:
    """Registra estado mejorado"""
    emp_u = empresa.upper()
    if emp_u not in verification_status:
        verification_status[emp_u] = {}
    if step not in verification_status[emp_u]:
        verification_status[emp_u][step] = {"ok": None, "messages": []}

    s = verification_status[emp_u][step]
    if ok is not None:
        current = s.get("ok")
        if current is None:
            s["ok"] = ok
        elif current and not ok:
            s["ok"] = False
    if message:
        msgs: List[str] = s.setdefault("messages", [])
        if message not in msgs:
            msgs.append(message)

def _build_verification_summary() -> List[str]:
    """Genera resumen mejorado"""
    lines: List[str] = []
    for emp in verification_order:
        status = verification_status.get(emp, {})
        lines.append(f"{emp}:")

        for step, data in status.items():
            estado = "[OK]" if data.get("ok") else "[ERROR]" if data.get("ok") is False else "[PENDIENTE]"
            mensajes = data.get("messages", [])
            lines.append(f"  - {step}: {estado}")
            for msg in mensajes:
                lines.append(f"    {msg}")
        lines.append("")

    while lines and not lines[-1]:
        lines.pop()
    return lines

# === Utilidades básicas (actualizadas) ===

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("empresa")
    p.add_argument("--input", required=True)
    p.add_argument("--respaldo")
    p.add_argument("--server")
    p.add_argument("--server-respaldo")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--skip-backup", action="store_true")
    return p.parse_args()

def _read_excel_pairs(path: Path) -> List[Pair]:
    xl = pd.ExcelFile(path)
    name = next((n for n in xl.sheet_names if n.strip().lower() == "cambiar key"), None)
    if not name:
        raise ValueError("Hoja 'Cambiar Key' no encontrada.")
    df = xl.parse(name, dtype=str)
    cols = {str(c).strip().upper(): c for c in df.columns}
    ca, cn = cols.get("KEY ACTUAL"), cols.get("KEY NUEVA")
    if not ca or not cn:
        raise ValueError("Faltan columnas 'KEY ACTUAL' y 'KEY NUEVA'.")
    pairs=[]
    for _,r in df.iterrows():
        a=_norm_key(r[ca]); n=_norm_key(r[cn])
        if a and n and a!=n:
            pairs.append((a.split(".",1)[0], n.split(".",1)[0]))
    if not pairs:
        raise ValueError("Sin filas válidas.")
    return pairs

def _load_groups_df(emp:str, out_root:str) -> pd.DataFrame:
    """Carga groups.csv"""
    for base in _candidate_base_dirs(emp, out_root):
        f = base / "HSH" / "groups.csv"
        if f.is_file():
            df = _read_csv_lenient(f)
            if df is not None:
                df.columns = [str(c).strip().upper() for c in df.columns]
                return df
    return pd.DataFrame()

def _load_lookup_tags(emp: str, out_root: str) -> Dict[str, Set[str]]:
    """Obtiene los tags (columna VALUE) por key desde lookup_table.csv."""
    tags_por_key: Dict[str, Set[str]] = defaultdict(set)
    for base in _candidate_base_dirs(emp, out_root):
        csv_path = base / "HSH" / "lookup_table.csv"
        if not csv_path.is_file():
            continue
        df = _read_csv_lenient(csv_path)
        if df is None or df.empty:
            continue
        columns = {str(col).strip().upper(): col for col in df.columns}
        key_col = columns.get("KEY") or columns.get("SCADA KEY") or columns.get("SCADA_KEY")
        value_col = columns.get("VALUE") or columns.get("TAG")
        if not key_col or not value_col:
            continue
        for _, row in df.iterrows():
            raw_key = str(row.get(key_col, "") or "").strip()
            if not raw_key:
                continue
            base_key = _norm_key(raw_key).split(".", 1)[0]
            tag = str(row.get(value_col, "") or "").strip()
            if not tag:
                continue
            tags_por_key.setdefault(base_key, set()).add(tag)
    return {key: set(values) for key, values in tags_por_key.items()}

def _suffixes_for_key(df: pd.DataFrame, base_key: str) -> Sequence[str]:
    """Obtiene sufijos"""
    if df.empty:
        return []
    uid_col = next((c for c in df.columns if str(c).strip().upper() in ["UID3", "UID_3"]), None)
    point_col = next((c for c in df.columns if str(c).strip().upper() == "POINTNAME"), None)
    if not uid_col or not point_col:
        return []
    mask = df[uid_col].astype(str).str.upper() == base_key
    suffixes = []
    for value in df.loc[mask, point_col].dropna().astype(str):
        value = value.strip()
        if value.startswith("."):
            value = value[1:]
        if value:
            suffixes.append(value.upper())
    return suffixes

def _collect_group_records(df: pd.DataFrame, base_key: str) -> List[Tuple[str, str, str]]:
    """Colecta registros"""
    if df.empty:
        return []
    columns = {str(col).strip().upper(): col for col in df.columns}
    uid3_col = columns.get("UID3") or columns.get("UID_3")
    cpid_col = columns.get("CPID")
    uid_col = columns.get("UID")
    point_col = columns.get("POINTNAME")
    if not uid3_col or not cpid_col or not uid_col:
        return []
    mask = df[uid3_col].astype(str).str.upper() == base_key
    if not mask.any():
        return []
    records = []
    for _, row in df.loc[mask].iterrows():
        cpid = str(row.get(cpid_col, "") or "").strip()
        uid = str(row.get(uid_col, "") or "").strip()
        point = str(row.get(point_col, "") or "").strip() if point_col else ""
        records.append((cpid, uid, point))
    return records

def _determine_scada_action(suffixes: Sequence[str], scada_entry: Optional[Dict]) -> Tuple[int, int]:
    """Determina acción SCADA"""
    analog_suffixes = {"VALUE", "ESTIMATED"}
    suf = {s.upper() for s in suffixes if s} if suffixes else set()
    source = (scada_entry or {}).get("source")
    tipo = 5 if (suf & analog_suffixes or source == "ANALOG") else 4
    bit = 2 if ("ESTIMATED" in suf) else 1
    return tipo, bit

def _scada_state_off(scada_entry: Optional[Dict], analog: bool) -> bool:
    """Verifica estado SCADA"""
    if not scada_entry:
        return False
    lsb = scada_entry.get("lsb")
    second = scada_entry.get("second")
    if analog:
        return (lsb in (0, None)) and (second in (0, None))
    return lsb in (0, None)

# === Verificación Dual-Side (mejorada) ===

def _verificar_estado_scada_dual(empresa_principal: str, empresa_respaldo: Optional[str],
                                key: str, scada_info_by_emp: Dict) -> Tuple[str, str, Optional[str], Optional[str]]:
    """Verifica estado en ambas empresas"""
    estado_p, src_p, ag_p, lsb_p, second_p = _read_scada_side(empresa_principal, key, scada_info_by_emp)

    if empresa_respaldo:
        estado_b, src_b, ag_b, lsb_b, second_b = _read_scada_side(empresa_respaldo, key, scada_info_by_emp)
    else:
        estado_b, src_b = "NO_ENCONTRADA", None

    print(f"[SCADA] {key}: {empresa_principal}={estado_p}, {empresa_respaldo or 'RESPALDO'}={estado_b}")
    return estado_p, estado_b, src_p, src_b

# === Bucle de Validación para Groups (mejorado) ===

def _validar_eliminacion_groups(empresa: str, key_vieja: str, max_intentos: int = 3) -> bool:
    """Valida eliminación en bucle"""
    out_root = output_root()

    for intento in range(max_intentos):
        # Cargar groups actualizado
        df_groups = _load_groups_df(empresa, out_root)
        records = _collect_group_records(df_groups, key_vieja)

        if not records:
            print(f"APPLY_OK:{empresa}:Key {key_vieja} eliminada de Groups (intento {intento+1})")
            _record_status(empresa, "groups_eliminacion", True, f"Key {key_vieja} eliminada en intento {intento+1}")
            return True

        print(f"APPLY_WARN:{empresa}:Key {key_vieja} todavía tiene {len(records)} registros en Groups (intento {intento+1})")
        _record_status(empresa, "groups_eliminacion", None, f"Key {key_vieja} con {len(records)} registros en intento {intento+1}")

        if intento < max_intentos - 1:
            print(f"MESSAGE:Reintentando verificación en 5 segundos...")
            time.sleep(5)

    print(f"APPLY_ERROR:{empresa}:No se pudo eliminar completamente {key_vieja} de Groups después de {max_intentos} intentos")
    _record_status(empresa, "groups_eliminacion", False, f"Key {key_vieja} no eliminada después de {max_intentos} intentos")
    return False


def _generar_reporte_verificacion_pairs(
    *,
    pairs: list[Pair],
    scada_info_by_emp: dict,
    records_by_empresa: dict,
    empresa: str,
    pi_sheet: Optional[tuple[list[str], list[list[str]]]] = None,
    include_post: Optional[dict] = None,
) -> str | None:
    """
    Genera el Excel de verificación con el formato Key actual / Key nueva.
    Si include_post viene, agrega hoja "Post-Delete" con estados posteriores.
    Si pi_sheet viene, agrega hoja "PI".
    Retorna la ruta si se creó correctamente y emite REPORT_PATH.
    """
    try:
        from openpyxl import Workbook  # type: ignore
    except Exception:
        return None

    out_dir = Path(output_root()) / "cambiar_key"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "Reporte_Cambiar_Key.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Verificacion"

    records_emp = records_by_empresa.get(empresa, {})

    def _scada_and_bit(entry: Optional[dict], suffixes: Sequence[str]) -> tuple[str, str]:
        if not entry:
            return "no existe", "apagado"
        analog = entry.get("source") == "ANALOG"
        off = _scada_state_off(entry, analog or bool({s for s in suffixes if s in {"VALUE", "ESTIMATED"}}))
        return "existe", "apagado" if off else "prendido"

    row_cursor = 1
    for old_base, new_base in pairs or [("", "")]:
        old_base = old_base or ""
        new_base = new_base or ""

        scada_old = scada_info_by_emp.get(empresa, {}).get(old_base)
        scada_new = scada_info_by_emp.get(empresa, {}).get(new_base)
        suffix_old = _suffixes_for_key(records_emp.get(old_base, pd.DataFrame()), old_base)
        suffix_new = _suffixes_for_key(records_emp.get(new_base, pd.DataFrame()), new_base)
        scada_state_old, bit_state_old = _scada_and_bit(scada_old, suffix_old)
        scada_state_new, bit_state_new = _scada_and_bit(scada_new, suffix_new)

        groups_old = "existe" if records_emp.get(old_base) else "no existe"
        groups_new = "existe" if records_emp.get(new_base) else "no existe"

        lookup_old = "existe" if old_base else "no existe"
        lookup_new = "no existe"

        ws.cell(row=row_cursor, column=1, value="Key actual")
        ws.cell(row=row_cursor, column=2, value=old_base)
        ws.cell(row=row_cursor, column=3, value="Key nueva")
        ws.cell(row=row_cursor, column=4, value=new_base)
        row_cursor += 1

        ws.cell(row=row_cursor, column=1, value="Scada")
        ws.cell(row=row_cursor, column=2, value=scada_state_old)
        ws.cell(row=row_cursor, column=3, value="Scada")
        ws.cell(row=row_cursor, column=4, value=scada_state_new)
        row_cursor += 1

        ws.cell(row=row_cursor, column=1, value="Lookuptable")
        ws.cell(row=row_cursor, column=2, value=lookup_old)
        ws.cell(row=row_cursor, column=3, value="Lookuptable")
        ws.cell(row=row_cursor, column=4, value=lookup_new)
        row_cursor += 1

        ws.cell(row=row_cursor, column=1, value="Groups")
        ws.cell(row=row_cursor, column=2, value=groups_old)
        ws.cell(row=row_cursor, column=3, value="Groups")
        ws.cell(row=row_cursor, column=4, value=groups_new)
        row_cursor += 1

        ws.cell(row=row_cursor, column=1, value="Bit")
        ws.cell(row=row_cursor, column=2, value=bit_state_old)
        ws.cell(row=row_cursor, column=3, value="Bit")
        ws.cell(row=row_cursor, column=4, value=bit_state_new)
        row_cursor += 2

    # Hoja post-Delete/Purge (opcional)
    if include_post:
        ws_post = wb.create_sheet("Post-Delete")
        post_pairs = include_post.get("pairs") or pairs
        post_scada = include_post.get("scada_info_by_emp") or scada_info_by_emp
        post_records = include_post.get("records_by_empresa") or records_by_empresa
        records_post_emp = post_records.get(empresa, {})
        row_cursor = 1
        for old_base, new_base in post_pairs or [("", "")]:
            old_base = old_base or ""
            new_base = new_base or ""
            scada_old = post_scada.get(empresa, {}).get(old_base)
            scada_new = post_scada.get(empresa, {}).get(new_base)
            suffix_old = _suffixes_for_key(records_post_emp.get(old_base, pd.DataFrame()), old_base)
            suffix_new = _suffixes_for_key(records_post_emp.get(new_base, pd.DataFrame()), new_base)
            scada_state_old, bit_state_old = _scada_and_bit(scada_old, suffix_old)
            scada_state_new, bit_state_new = _scada_and_bit(scada_new, suffix_new)
            groups_old = "existe" if records_post_emp.get(old_base) else "no existe"
            groups_new = "existe" if records_post_emp.get(new_base) else "no existe"

            ws_post.cell(row=row_cursor, column=1, value="Key actual")
            ws_post.cell(row=row_cursor, column=2, value=old_base)
            ws_post.cell(row=row_cursor, column=3, value="Key nueva")
            ws_post.cell(row=row_cursor, column=4, value=new_base)
            row_cursor += 1

            ws_post.cell(row=row_cursor, column=1, value="Scada")
            ws_post.cell(row=row_cursor, column=2, value=scada_state_old)
            ws_post.cell(row=row_cursor, column=3, value="Scada")
            ws_post.cell(row=row_cursor, column=4, value=scada_state_new)
            row_cursor += 1

            ws_post.cell(row=row_cursor, column=1, value="Lookuptable")
            ws_post.cell(row=row_cursor, column=2, value="existe" if old_base else "no existe")
            ws_post.cell(row=row_cursor, column=3, value="Lookuptable")
            ws_post.cell(row=row_cursor, column=4, value="no existe")
            row_cursor += 1

            ws_post.cell(row=row_cursor, column=1, value="Groups")
            ws_post.cell(row=row_cursor, column=2, value=groups_old)
            ws_post.cell(row=row_cursor, column=3, value="Groups")
            ws_post.cell(row=row_cursor, column=4, value=groups_new)
            row_cursor += 1

            ws_post.cell(row=row_cursor, column=1, value="Bit")
            ws_post.cell(row=row_cursor, column=2, value=bit_state_old)
            ws_post.cell(row=row_cursor, column=3, value="Bit")
            ws_post.cell(row=row_cursor, column=4, value=bit_state_new)
            row_cursor += 2

    # Hoja PI (opcional)
    if pi_sheet:
        headers, rows = pi_sheet
        ws_pi = wb.create_sheet("PI")
        ws_pi.append(headers)
        for r in rows:
            ws_pi.append(r)

    try:
        wb.save(report_path)
    except Exception:
        return None

    print(f"REPORT_PATH:{report_path}")
    return str(report_path)

# === Operaciones SCADA (ACTUALIZADAS) ===

def _ejecutar_comando_scada_guaranteed(empresa: str, host: str, base_key: str, tipo: int, bit: int, encender: bool = False) -> bool:
    """Ejecuta comando SCADA  con verificación REAL"""
    try:
        valor = 1 if encender else 0
        accion = "ENCENDER" if encender else "APAGAR"

        print(f"MESSAGE:Conectando a {host} para {accion} bits  de {base_key} (tipo={tipo}, bit={bit})")

        # Usar logger mejorado
        log_dir = Path(output_root()).resolve() / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger, logger_console = Logger.initlog(str(log_dir / "scada_commands_guaranteed.log"))

        client = sshserver(host, logger, logger_console)
        if client is None:
            raise RuntimeError("sshserver devolvió None")

        cmd = f". ~/.bash_profile && dbset -k 10 {tipo} 12 {base_key} {bit} = {valor}"
        print(f"MESSAGE:Ejecutando comando SCADA : {cmd}")

        stdin, stdout, stderr = client.exec_command(cmd)
        rc = stdout.channel.recv_exit_status()

        if rc == 0:
            descriptor = f"{empresa}|CC|{base_key}|{tipo}:{bit}"
            if encender:
                print(f"SCADA_ENABLE:{descriptor}")
            else:
                print(f"SCADA_DISABLE:{descriptor}")
            print(f"APPLY_OK:{empresa}:Bits {accion.lower()} para {base_key} (rc={rc})")
            _record_status(empresa, "scada_bits", True, f"Bits {accion.lower()} para {base_key}")
            return True
        else:
            err = stderr.read().decode("utf-8", "ignore").strip()
            print(f"APPLY_ERROR:{empresa}:Fallo {accion} {base_key}: {err} (rc={rc})")
            _record_status(empresa, "scada_bits", False, f"Error {accion} {base_key}: {err} (rc={rc})")
            return False

    except Exception as exc:
        print(f"APPLY_ERROR:{empresa}:Error SCADA {host}: {exc}")
        _record_status(empresa, "scada_bits", False, f"Error conexión {host}: {exc}")
        return False
    finally:
        try:
            if 'client' in locals():
                client.close()
        except Exception:
            pass

def _verificar_bits_scada_guaranteed(empresa: str, key: str, scada_info_by_emp: Dict, deberian_estar_apagados: bool = True) -> bool:
    """Verifica estado real de bits en SCADA """
    estado, source, ag, lsb, second = _read_scada_side(empresa, key, scada_info_by_emp)

    if deberian_estar_apagados:
        apagado = estado == "OFF"
        print(f"VERIFICATION_STATUS:{empresa}:Key {key} bits apagados: {apagado}")
        _record_status(empresa, "scada_verificacion", apagado, f"Key {key} bits apagados: {apagado}")
        return apagado
    else:
        encendido = estado == "ON"
        print(f"VERIFICATION_STATUS:{empresa}:Key {key} bits encendidos: {encendido}")
        _record_status(empresa, "scada_verificacion", encendido, f"Key {key} bits encendidos: {encendido}")
        return encendido

# === Operaciones MongoDB (ACTUALIZADAS) ===

def _modificar_lookup_tables_guaranteed(
    empresa: str,
    server: Optional[str],
    server_respaldo: Optional[str],
    pairs: List[Pair],
    skip_backup: bool = False,
) -> Tuple[int, Dict[str, int]]:
    """
    MODIFICACIÓN : Modifica lookup_tables para AMBAS empresas
    usando conexiones explícitas.
    """
    if not pairs:
        print("APPLY_SKIPPED:No hay pares para modificar en lookup_tables")
        return 0, {}

    log_dir = Path(output_root()).resolve() / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "hsh_cambiar_key.log"
    logger, logger_console = Logger.initlog(str(log_path))

    empresa_norm = _norm_key(empresa)
    targets: List[Tuple[str, str]] = []  # (empresa, servidor)

    # ✅ : Definir explícitamente AMBAS conexiones
    # Empresa principal (SIEMPRE requerida)
    if server:
        targets.append((empresa_norm, server))
        print(f"APPLY_SERVER:{empresa_norm}:{server}")
    else:
        raise ValueError("Servidor principal no proporcionado - REQUERIDO")

    # Empresa respaldo (SIEMPRE que exista respaldo)
    respaldo = None if skip_backup else _related_company(empresa_norm)
    if respaldo:
        if server_respaldo:
            targets.append((respaldo, server_respaldo))
            print(f"APPLY_SERVER:{respaldo}:{server_respaldo}")
        else:
            # ✅ : Si hay respaldo pero no servidor, usar lógica de respaldo
            respaldo_candidates = _related_servers(server, empresa_norm)
            if respaldo_candidates:
                targets.append((respaldo, respaldo_candidates[0]))
                print(f"APPLY_SERVER:{respaldo}:{respaldo_candidates[0]} (derivado)")
            else:
                print(f"APPLY_WARN:{respaldo}:No se pudo determinar servidor respaldo, omitiendo")

    if not targets:
        raise RuntimeError("No se pudo determinar conexiones para modificación Mongo")

    total_modified = 0
    modified_by_empresa: Dict[str, int] = {}

    for target_empresa, target_server in targets:
        client = tunnel = None
        cert_path = key_path = None
        modified_current = 0

        try:
            # ✅ : Usar el servidor proporcionado explícitamente
            print(f"MESSAGE:Conectando a MongoDB : {target_empresa} -> {target_server}")
            client, tunnel, cert_path, key_path = conexion_hsh(target_empresa, target_server, logger, logger_console)
            chosen_server = getattr(client, "_hsh_host", target_server)
            print(f"APPLY_SERVER_CONFIRMED:{target_empresa}:{chosen_server}")

            db = client[_target_db(target_empresa)]
            print(f"MESSAGE:Conexión MongoDB  establecida para {target_empresa}")

            for old_key, new_key in pairs:
                try:
                    # ✅ : Query de actualización con $regex y $replaceOne
                    print(f"MESSAGE:Modificando lookup_tables: {old_key} -> {new_key} en {target_empresa}")
                    result = db.lookup_tables.update_many(
                        {"key": {"$regex": f"^{old_key}"}},
                        [{"$set": {"key": {"$replaceOne": {
                            "input": "$key",
                            "find": old_key,
                            "replacement": new_key
                        }}}}]
                    )

                    modified_current += result.modified_count
                    print(f"MONGO_SUMMARY:{target_empresa}:Actualizados {result.modified_count} registros: {old_key}->{new_key}")
                    _record_status(target_empresa, "modificacion_mongo", True,
                                  f"Actualizados {result.modified_count} registros: {old_key}->{new_key}")

                except Exception as exc:
                    print(f"APPLY_ERROR:{target_empresa}:Error actualizando {old_key}->{new_key}: {exc}")
                    _record_status(target_empresa, "modificacion_mongo", False,
                                  f"Error actualizando {old_key}->{new_key}: {exc}")

            modified_by_empresa[target_empresa] = modified_current
            total_modified += modified_current

            print(f"APPLY_OK:{target_empresa}:Modificados {modified_current} registros en lookup_tables ")

        except Exception as exc:
            print(f"APPLY_ERROR:{target_empresa}:Error conexión Mongo : {exc}")
            _record_status(target_empresa, "modificacion_mongo", False, f"Error conexión : {exc}")
        finally:
            # Limpieza de recursos
            try:
                if client:
                    client.close()
                    print(f"MESSAGE:Conexión MongoDB cerrada para {target_empresa}")
            except Exception:
                pass
            try:
                if tunnel and getattr(tunnel, "is_alive", lambda: False)():
                    tunnel.stop()
            except Exception:
                pass
            for temp in (cert_path, key_path):
                if temp and os.path.exists(temp):
                    try:
                        os.remove(temp)
                    except Exception:
                        pass

    print(f"APPLY_OK_TOTAL:{total_modified}")
    return total_modified, modified_by_empresa

# === Reportes (actualizados) ===

def _prepare_reports_dir(empresa: str, out_root: str) -> Path:
    base = Path(out_root) / "out" / "cambiar_key" / empresa.upper()
    base.mkdir(parents=True, exist_ok=True)
    return base

# === Core Principal ===

def _main() -> int:
    args = _parse_args()
    skip_backup = bool(args.skip_backup)
    empresa = _norm_key(args.empresa)
    if not empresa:
        raise ValueError("Debes indicar una empresa válida.")

    respaldo = _norm_key(args.respaldo) if args.respaldo and not skip_backup else None
    if skip_backup:
        args.server_respaldo = None

    # ✅ VALIDACIÓN : Verificar servidores para AMBAS empresas
    if args.apply:
        if not args.server:
            raise ValueError("Cuando uses --apply debes indicar --server (requerido).")
        if respaldo and not args.server_respaldo:
            # ✅ : Intentar derivar servidor respaldo si no se proporciona
            print(f"APPLY_WARN:Empresa respaldo {respaldo} definida pero sin --server-respaldo, intentando derivar...")
            respaldo_candidates = _related_servers(args.server, empresa)
            if respaldo_candidates:
                args.server_respaldo = respaldo_candidates[0]
                print(f"APPLY_INFO:Usando servidor respaldo derivado: {args.server_respaldo}")
            else:
                raise ValueError(f"Empresa respaldo {respaldo} definida pero no se pudo determinar --server-respaldo.")

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {input_path}")

    pairs = _read_excel_pairs(input_path)
    if not pairs:
        raise ValueError("Se requieren pares de claves para procesar.")

    out_root = output_root()
    empresas_a_cargar = [empresa]
    if respaldo:
        empresas_a_cargar.append(respaldo)

    # Inicializar sistema de estado
    global verification_status, verification_order
    verification_status.clear()
    verification_order.clear()

    for emp in empresas_a_cargar:
        verification_order.append(emp.upper())
        _record_status(emp, "inicializacion", True, "Proceso  iniciado")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # === INFORMACIÓN DETALLADA  EN LOGS ===
    print("MESSAGE:=== INICIO PROCESO CAMBIO KEY ===")
    print(f"MESSAGE:Empresa: {empresa}")
    print(f"MESSAGE:Respaldo: {respaldo}")
    print(f"MESSAGE:Archivo Excel: {input_path}")
    print(f"MESSAGE:Pares a procesar: {len(pairs)}")
    for i, (old, new) in enumerate(pairs, 1):
        print(f"MESSAGE:  {i}. {old} -> {new}")
    print(f"MESSAGE:Modo aplicar: {args.apply}")
    print(f"MESSAGE:Modo check-only: {args.check_only}")
    print(f"MESSAGE:Servidor principal: {args.server}")
    print(f"MESSAGE:Servidor respaldo: {args.server_respaldo}")

    # Cargar dumps locales
    print(f"MESSAGE:Cargando datos SCADA y HSH ...")
    _, scada_info_by_emp, scada_missing = _load_scada_data(out_root, empresas_a_cargar)
    for warning in scada_missing:
        print(f"MESSAGE:{warning}")

    groups_por_empresa = {}
    lookup_tags_por_empresa: Dict[str, Dict[str, Set[str]]] = {}
    for emp in empresas_a_cargar:
        try:
            groups_por_empresa[emp] = _load_groups_df(emp, out_root)
            print(f"MESSAGE:Groups cargado para {emp}: {len(groups_por_empresa[emp])} registros")
            _record_status(emp, "carga_datos", True, f"Groups cargado: {len(groups_por_empresa[emp])} registros")
            lookup_tags_por_empresa[emp] = _load_lookup_tags(emp, out_root)
            if not lookup_tags_por_empresa[emp]:
                print(f"MESSAGE:ADVERTENCIA:No se hallaron tags en lookup_table.csv para {emp}")
        except Exception as exc:
            if args.check_only:
                print(f"MESSAGE:ADVERTENCIA: {exc}")
                groups_por_empresa[emp] = pd.DataFrame()
                lookup_tags_por_empresa[emp] = {}
                _record_status(emp, "carga_datos", False, str(exc))
            else:
                raise

    # === INFORMACIÓN DETALLADA DE GROUPS ANTES DE CAMBIOS ===
    print("MESSAGE:=== ESTADO INICIAL EN GROUPS ===")
    for old_base, new_base in pairs:
        for emp in empresas_a_cargar:
            records = _collect_group_records(groups_por_empresa.get(emp, pd.DataFrame()), old_base)
            if records:
                print(f"MESSAGE:Empresa {emp} - Key {old_base}: {len(records)} registros en groups")
                _record_status(emp, "estado_inicial", None, f"Key {old_base}: {len(records)} registros en groups")
                for cpid, uid, point in records[:3]:  # Mostrar primeros 3
                    print(f"MESSAGE:  - CPID:{cpid} UID:{uid} POINT:{point}")

    errores = []
    advertencias = []
    scada_disable = []
    scada_enable = []
    scada_domains: Tuple[str, ...] = ("CC", "QA")  # ✅ : TODOS los dominios

    # Estructuras para tracking
    records_by_empresa = defaultdict(dict)
    pi_tags_new_by_empresa = defaultdict(set)  # ✅ : Para TAGS específicos, no keys
    server_map = {empresa: args.server}
    if respaldo:
        server_map[respaldo] = args.server_respaldo

    # === VALIDACIONES Y PREPARACIÓN (con verificación dual-side) ===
    print("MESSAGE:=== VALIDACIONES ===")
    for old_base, new_base in pairs:
        print(f"MESSAGE:Procesando par : {old_base} -> {new_base}")

        # Obtener sufijos de la key actual
        suffixes = _suffixes_for_key(groups_por_empresa.get(empresa, pd.DataFrame()), old_base)
        print(f"MESSAGE:  Sufijos encontrados para {old_base}: {list(suffixes)}")

        # Verificación dual-side  para key NUEVA
        estado_p, estado_b, src_p, src_b = _verificar_estado_scada_dual(empresa, respaldo, new_base, scada_info_by_emp)
        scada_entry_new = scada_info_by_emp.get(empresa, {}).get(new_base)

        if not scada_entry_new:
            error_msg = f"La clave nueva {new_base} no existe en los dumps SCADA de {empresa}."
            print(f"MESSAGE:  ERROR: {error_msg}")
            errores.append(error_msg)
            _record_status(empresa, "validacion_key_nueva", False, error_msg)
        else:
            analog_expected = bool({s for s in suffixes if s in {"VALUE", "ESTIMATED"}})
            state_off = _scada_state_off(scada_entry_new, analog_expected or scada_entry_new.get("source") == "ANALOG")
            print(f"MESSAGE:  Key nueva {new_base} existe en SCADA, bits apagados: {state_off}")
            _record_status(empresa, "validacion_key_nueva", state_off,
                          f"Key {new_base} existe, bits apagados: {state_off}")

            if not state_off:
                error_msg = f"La clave nueva {new_base} tiene bits de envío activos en SCADA ({empresa})."
                print(f"MESSAGE:  ERROR: {error_msg}")
                errores.append(error_msg)

        # ✅ : Programar APAGADO de key ACTUAL en TODOS los dominios
        estado_p_old, estado_b_old, src_p_old, src_b_old = _verificar_estado_scada_dual(empresa, respaldo, old_base, scada_info_by_emp)
        scada_entry_old = scada_info_by_emp.get(empresa, {}).get(old_base)

        if scada_entry_old:
            analog_old = (scada_entry_old.get("source") == "ANALOG")
            off = _scada_state_off(scada_entry_old, analog_old or bool({s for s in suffixes if s in {'VALUE','ESTIMATED'}}))
            if not off:
                tipo, bit = _determine_scada_action(suffixes, scada_entry_old)
                for dominio in scada_domains:  # ✅ TODOS los dominios
                    scada_disable.append((empresa, dominio, old_base, tipo, bit))
                    if args.apply:
                        print(f"SCADA_DISABLE:{empresa}|{dominio}|{old_base}|{tipo}:{bit}")
                    print(f"MESSAGE:  Programado APAGADO bits ({dominio}) para {old_base}: tipo={tipo}, bit={bit}")
                _record_status(empresa, "programacion_apagado", None, f"Key {old_base}: tipo={tipo}, bit={bit}")

        # ✅ : Programar ENCENDIDO de key NUEVA en TODOS los dominios
        if scada_entry_new:
            tipo_new, bit_new = _determine_scada_action(suffixes, scada_entry_new)
            for dominio in scada_domains:  # ✅ TODOS los dominios
                scada_enable.append((empresa, dominio, new_base, tipo_new, bit_new))
                print(f"MESSAGE:  Programado ENCENDIDO bits ({dominio}) para {new_base}: tipo={tipo_new}, bit={bit_new}")
            _record_status(empresa, "programacion_encendido", None, f"Key {new_base}: tipo={tipo_new}, bit={bit_new}")

        # Respaldos
        if respaldo:
            suffixes_res = _suffixes_for_key(groups_por_empresa.get(respaldo, pd.DataFrame()), old_base)
            scada_entry_old_res = scada_info_by_emp.get(respaldo, {}).get(old_base)
            if scada_entry_old_res:
                analog_old_res = scada_entry_old_res.get("source") == "ANALOG"
                off_res = _scada_state_off(
                    scada_entry_old_res,
                    analog_old_res or bool({s for s in suffixes_res if s in {'VALUE', 'ESTIMATED'}}),
                )
                if not off_res:
                    tipo_res, bit_res = _determine_scada_action(suffixes_res or suffixes, scada_entry_old_res)
                    for dominio in scada_domains:  # ✅ TODOS los dominios
                        scada_disable.append((respaldo, dominio, old_base, tipo_res, bit_res))
                        if args.apply:
                            print(f"SCADA_DISABLE:{respaldo}|{dominio}|{old_base}|{tipo_res}:{bit_res}")
                        print(f"MESSAGE:  Programado APAGADO bits respaldo  {respaldo} ({dominio}) para {old_base}")
                    _record_status(respaldo, "programacion_apagado", None, f"Key {old_base}: tipo={tipo_res}, bit={bit_res}")

            scada_entry_new_res = scada_info_by_emp.get(respaldo, {}).get(new_base)
            if scada_entry_new_res:
                tipo_res_new, bit_res_new = _determine_scada_action(suffixes_res or suffixes, scada_entry_new_res)
                for dominio in scada_domains:  # ✅ TODOS los dominios
                    scada_enable.append((respaldo, dominio, new_base, tipo_res_new, bit_res_new))
                    print(f"MESSAGE:  Programado ENCENDIDO bits respaldo  {respaldo} ({dominio}) para {new_base}")
                _record_status(respaldo, "programacion_encendido", None, f"Key {new_base}: tipo={tipo_res_new}, bit={bit_res_new}")

        # Capturar registros en groups para Delete/Purge
        records = _collect_group_records(groups_por_empresa.get(empresa, pd.DataFrame()), old_base)
        if records:
            records_by_empresa[empresa][old_base] = records
            print(f"MESSAGE:  {len(records)} registros en groups para {old_base} ({empresa})")
            for cpid, uid, point in records[:3]:
                print(f"MESSAGE:    - CPID:{cpid} UID:{uid} POINT:{point}")
        else:
            warning_msg = f"No se encontraron registros en groups.csv para {old_base} ({empresa})."
            print(f"MESSAGE:ADVERTENCIA:{warning_msg}")
            advertencias.append(warning_msg)

        if respaldo:
            records_res = _collect_group_records(groups_por_empresa.get(respaldo, pd.DataFrame()), old_base)
            if records_res:
                records_by_empresa[respaldo][old_base] = records_res
                print(f"MESSAGE:  {len(records_res)} registros en groups respaldo {respaldo}")
            else:
                print(f"MESSAGE:ADVERTENCIA:No se encontraron registros en groups respaldo {respaldo} para {old_base}")

        # Preparar TAGS PI desde lookup_table (empresa principal)
        lookup_dict = lookup_tags_por_empresa.get(empresa, {})
        moved_tags = lookup_dict.pop(old_base, set())
        if moved_tags:
            lookup_dict.setdefault(new_base, set()).update(moved_tags)
            moved_txt = ", ".join(sorted(moved_tags)) or "SIN_TAGS"
            print(f"MESSAGE:PI_TAGS_MOVED:{empresa}:{old_base}->{new_base}:{moved_txt}")
        lookup_tags = lookup_dict.get(new_base, set())
        if not lookup_tags and moved_tags:
            lookup_tags = moved_tags
        if lookup_tags:
            for tag in sorted(lookup_tags):
                pi_tags_new_by_empresa[empresa].add(tag)
                print(f"PI_TAG:{empresa}|{tag}")
            _record_status(empresa, "preparacion_tags", True, f"{len(lookup_tags)} tags PI asociados")
        else:
            warning_msg = f"No se encontraron tags en lookup_table para {new_base if new_base else old_base} ({empresa})."
            print(f"MESSAGE:ADVERTENCIA:{warning_msg}")
            advertencias.append(warning_msg)
            _record_status(empresa, "preparacion_tags", False, warning_msg)

    if errores:
        for err in errores:
            print(f"MESSAGE:{err}")
        return 1

    if advertencias:
        for warn in advertencias:
            print(f"MESSAGE:{warn}")

    # === MODO SOLO VERIFICACIÓN ===
    if args.check_only:
        print("MESSAGE:=== VERIFICACION POST-ELIMINACION ===")
        pending_found = False
        scada_pending = False
        for old_base, _ in pairs:
            for emp in empresas_a_cargar:
                records = _collect_group_records(groups_por_empresa.get(emp, pd.DataFrame()), old_base)
                if records:
                    pending_found = True
                    print(f"PENDING_KEY:{old_base}")
                    print(f"MESSAGE:{emp}: la clave {old_base} aun tiene {len(records)} registros en groups.")
        for old_base, _ in pairs:
            for emp in empresas_a_cargar:
                scada_entry = scada_info_by_emp.get(emp, {}).get(old_base)
                if not scada_entry:
                    continue
                suffixes_emp = _suffixes_for_key(groups_por_empresa.get(emp, pd.DataFrame()), old_base)
                analog = scada_entry.get("source") == "ANALOG"
                still_on = not _scada_state_off(scada_entry, analog or bool({s for s in suffixes_emp if s in {'VALUE', 'ESTIMATED'}}))
                if still_on:
                    tipo_chk, bit_chk = _determine_scada_action(suffixes_emp, scada_entry)
                    scada_pending = True
                    for dominio in scada_domains:  # ✅ VERIFICAR TODOS los dominios
                        descriptor = f"{emp}|{dominio}|{old_base}|{tipo_chk}:{bit_chk}"
                        print(f"SCADA_STILL_ON:{descriptor}")
                        print(f"MESSAGE:{emp} ({dominio}): bit activo detectado para {old_base} (tipo {tipo_chk}, bit {bit_chk}).")
        if not pending_found and not scada_pending:
            print("MESSAGE:Verificacion completa: no se encontraron registros ni bits activos.")
        # Generar reporte de verificación desde el script
        ruta_rep = _generar_reporte_verificacion_pairs(
            pairs=pairs,
            scada_info_by_emp=scada_info_by_emp,
            records_by_empresa=records_by_empresa,
            empresa=empresa,
        )
        if ruta_rep:
            print(f"REPORT_PATH:{ruta_rep}")
        return 0

    if not args.apply:
        print("MESSAGE:=== RESUMEN VALIDACION ===")
        print(f"MESSAGE:Empresa principal: {empresa}")
        print(f"MESSAGE:Empresa respaldo: {respaldo}" if respaldo else "MESSAGE:Sin respaldo")
        print(f"MESSAGE:Pares procesados: {len(pairs)}")
        verification_summary = _build_verification_summary()
        for line in verification_summary:
            print(f"VERIFICATION_STATUS:{line}")
        print("MESSAGE:No se aplicaron cambios. Use --apply para ejecutar el cambio completo.")
        # Generar reporte de verificación desde el script
        ruta_rep = _generar_reporte_verificacion_pairs(
            pairs=pairs,
            scada_info_by_emp=scada_info_by_emp,
            records_by_empresa=records_by_empresa,
            empresa=empresa,
        )
        if ruta_rep:
            print(f"REPORT_PATH:{ruta_rep}")
        return 0

    # === MODO APLICACIÓN - FLUJO COMPLETO ===

    # FASE 1: MODIFICACIÓN EN MONGO  para AMBAS EMPRESAS
    if skip_backup:
        print("MESSAGE:=== MODIFICANDO LOOKUP_TABLES EN MONGO (EMPRESA UNICA) ===")
    else:
        print("MESSAGE:=== MODIFICANDO LOOKUP_TABLES EN MONGO (PRINCIPAL + RESPALDO) ===")

    # Pasar ambos servidores explicitamente
    total_modified, modified_by_empresa = _modificar_lookup_tables_guaranteed(
        empresa,
        args.server,  # Servidor principal
        args.server_respaldo,  # Servidor respaldo
        pairs,
        skip_backup=skip_backup
    )

    # Reportar resultados  por empresa
    for emp, count in modified_by_empresa.items():
        print(f"MONGO_SUMMARY:{emp}:Modificados {count} registros en lookup_tables")
        _record_status(emp, "modificacion_mongo", count > 0, f"Modificados {count} registros")

    # Reporte consolidado
    if respaldo and respaldo in modified_by_empresa:
        print(f"MONGO_SUMMARY:CONSOLIDADO: {empresa}={modified_by_empresa.get(empresa, 0)}, {respaldo}={modified_by_empresa.get(respaldo, 0)}")
    else:
        print(f"MONGO_SUMMARY:CONSOLIDADO: {empresa}={modified_by_empresa.get(empresa, 0)}")

    # FASE 2: GENERAR DELETE/PURGE  PARA KEY ACTUAL
    print(f"MESSAGE:=== GENERANDO ARCHIVOS DELETE/PURGE ===")
    all_delete_paths = []
    all_purge_paths = []
    info_lines = []

    for emp, mapping in records_by_empresa.items():
        if not mapping:
            continue
        command_rows: List[Tuple[str, str]] = []
        human_lines: List[str] = []
        human_lines.append(f"=== ARCHIVOS  PARA {emp} ===")
        for base_key, rows in mapping.items():
            if not rows:
                continue
            primary = next(((cpid, uid) for cpid, uid, _ in rows if cpid and uid), None)
            if primary is None and rows:
                primary = (rows[0][0], rows[0][1])
            if not primary or not primary[0] or not primary[1]:
                warning = f"{emp} - {base_key}: sin CPID/UID valido para Delete/Purge "
                human_lines.append(f"ADVERTENCIA: {warning}")
                _record_status(emp, "generacion_archivos", False, warning)
                continue
            command_rows.append(primary)
            human_lines.append(f"Key: {base_key} - {len(rows)} registros (se usara {primary[0]}|{primary[1]})")
            for cpid, uid, point in rows[:3]:
                if point:
                    human_lines.append(f"  - CPID:{cpid} | UID:{uid} | POINT:{point}")
        if not command_rows:
            continue

        report_dir = _prepare_reports_dir(emp, out_root)
        delete_path = report_dir / f"{emp.upper()}_delete_UIDs.csv"
        purge_path = report_dir / f"{emp.upper()}_purge_UIDs.csv"

        _write_commands(delete_path, "Delete", command_rows, timestamp)
        _write_commands(purge_path, "Purge", command_rows, timestamp)

        all_delete_paths.append(delete_path)
        all_purge_paths.append(purge_path)
        info_lines.extend(human_lines)

        print(f"DELETE_FILE:{delete_path}")
        print(f"PURGE_FILE:{purge_path}")
        print(f"APPLY_OK:{emp}:Generados {len(command_rows)} comandos (uno por key)")
        _record_status(emp, "generacion_archivos", True, f"Generadas {len(command_rows)} filas (una por key)")

    # FASE 3: ACCION MANUAL Y PREPARACION DE PASOS POSTERIORES
    print(f"MESSAGE:=== ACCION MANUAL REQUERIDA ===")
    print(f"MESSAGE:Ejecuta los archivos Delete/Purge generados para eliminar las keys antiguas en groups.")
    manual_keys = sorted({old for old, _ in pairs})
    for key in manual_keys:
        print(f"PENDING_KEY:{key}")
    _record_status(empresa, "pendiente_groups", None, "Limpieza manual requerida en groups.")

    if scada_enable:
        print("MESSAGE:Los bits de las keys nuevas se encenderan despues de confirmar la limpieza.")
    for emp, dominio, base_key, tipo, bit in scada_enable:
        descriptor = f"{emp}|{dominio}|{base_key}|{tipo}:{bit}"
        print(f"SCADA_ENABLE:{descriptor}")

    if pi_tags_new_by_empresa:
        print("MESSAGE:Se prepararon TAGS para consulta PI (pendiente tras encender keys nuevas).")
        for emp, tags in sorted(pi_tags_new_by_empresa.items()):
            for tag in sorted(tags):
                print(f"PI_TAG:{emp}|{tag}")
    else:
        print(f"MESSAGE:No se identificaron tags PI asociados a las claves procesadas.")

    # FASE 4: REPORTES FINALES
    report_lines = [
        f"=== REPORTE DETALLADO CAMBIO SCADA KEY ===",
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Empresa principal: {empresa}",
        f"Empresa respaldo: {respaldo}" if respaldo else "Sin respaldo",
        f"Servidor principal: {args.server}",
        f"Servidor respaldo: {args.server_respaldo}" if args.server_respaldo else "No especificado",
        f"Archivo origen: {input_path}",
        f"Total pares: {len(pairs)}",
        "",
        "=== MODIFICACIONES MONGO DB ===",
    ]

    # Agregar detalles de modificación  por empresa
    for emp, count in modified_by_empresa.items():
        report_lines.append(f"- {emp}: {count} registros modificados en lookup_tables")

    report_lines.extend([
        "",
        "=== TAGS  PREPARADOS PARA PI ===",
    ])

    # Agregar detalles de tags PI
    for emp, tags in sorted(pi_tags_new_by_empresa.items()):
        report_lines.append(f"- {emp}: {len(tags)} tags específicos ")
        for tag in sorted(tags)[:5]:  # Mostrar primeros 5 tags como ejemplo
            report_lines.append(f"  • {tag}")
        if len(tags) > 5:
            report_lines.append(f"  • ... y {len(tags) - 5} tags más")

    report_lines.extend([
        "",
        "=== RESUMEN EJECUCIÓN ===",
        f"Archivos Delete generados: {len(all_delete_paths)}",
        f"Archivos Purge generados: {len(all_purge_paths)}",
        f"Keys pendientes de eliminar manualmente: {', '.join(manual_keys) if manual_keys else 'Ninguna'}",
        f"Bits nuevos pendientes de encender: {len(scada_enable)}",
        "",
    ])

    # Agregar resumen de verificación
    verification_summary = _build_verification_summary()
    report_lines.extend(["=== ESTADO DE VERIFICACIÓN ==="])
    report_lines.extend(verification_summary)

    for line in report_lines:
        print(f"MESSAGE:{line}")
    if info_lines:
        print("MESSAGE:=== DETALLE DELETE/PURGE ===")
        for line in info_lines:
            print(f"MESSAGE:{line}")
    print("MESSAGE:=== PROCESO  COMPLETADO ===")

    # Mostrar resumen final
    print(f"VERIFICATION_STATUS:=== RESUMEN FINAL ===")
    for line in verification_summary:
        print(f"VERIFICATION_STATUS:{line}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR:{e}", file=sys.stderr)
        raise SystemExit(1)
