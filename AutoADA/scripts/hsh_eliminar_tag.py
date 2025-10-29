# scripts/hsh_eliminar_tag.py
"""Genera archivos Delete/Purge y elimina (opcionalmente) tags HSH existentes por EMPRESA.
- Opera UNA empresa por ejecución (el handler debe llamar 2 veces: principal y respaldo).
- Emite DELETE_KEYS robusto, y (en validar) LOOKUP_WOULD_DELETE con la lista exacta que borraría.
- Si --apply: borra en Mongo por lista exacta (no regex), y reporta LOOKUP_DELETE/LOOKUP_REMAINING.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

# ===================== Cargas dinámicas (Logger / conexion_hsh) =====================

def _load_dependencies():
    logger_mod = None
    conexion = None
    try:
        from scripts import _Logger as _logger  # type: ignore
        from scripts.functions import conexion_hsh as _conexion  # type: ignore
        logger_mod = _logger
        conexion = _conexion
        return logger_mod, conexion
    except Exception:
        pass
    try:
        import _Logger as _logger  # type: ignore
        from functions import conexion_hsh as _conexion  # type: ignore
        logger_mod = _logger
        conexion = _conexion
        return logger_mod, conexion
    except Exception:
        pass
    try:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as _logger  # type: ignore
        from functions import conexion_hsh as _conexion  # type: ignore
        logger_mod = _logger
        conexion = _conexion
    except Exception:
        logger_mod = None
        conexion = None
    return logger_mod, conexion

Logger, conexion_hsh = _load_dependencies()

def _target_db(empresa: str) -> str:
    mapping = {
        "REPS": "PI_REPS",
        "REPP": "PI_REPP",
        "ITCO": "PI_ITCO",
        "TRA":  "PI_TRA",
    }
    return mapping.get((empresa or "").upper(), (empresa or "").upper())

try:
    from utils.paths import output_root
except Exception:  # pragma: no cover
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
    from utils.paths import output_root  # type: ignore

# ===================== Utilidades básicas =====================

def _norm_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    return str(v).strip()

def _norm_key(v) -> str:
    t = _norm_str(v)
    return t.upper() if t else ""

def _emit_summary(lines: Iterable[str]) -> None:
    for ln in lines:
        ln = (ln or "").strip()
        if ln:
            print(f"SUMMARY:{ln}")

# ===================== Lectura input =====================

def _read_input(path: Path) -> pd.DataFrame:
    sheet_name = "Eliminar Tag"
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
    except ValueError as exc:
        raise ValueError(f"No se pudo leer la hoja '{sheet_name}' en {path}: {exc}") from exc
    if df.empty:
        raise ValueError("El archivo de entrada esta vacio.")
    original = list(df.columns)
    rename: Dict[str, str] = {}
    for col in original:
        up = col.strip().upper()
        if up in {"SCADA_KEY", "SCADAKEY", "SCADA KEY"}:
            rename[col] = "SCADA_KEY"
        elif up in {"TAG", "NOMBRE TAG"}:
            rename[col] = "TAG"
    df = df.rename(columns=rename)
    if "SCADA_KEY" not in df.columns:
        raise ValueError("La hoja debe contener una columna 'SCADA_KEY'.")
    if "TAG" not in df.columns:
        df["TAG"] = ""
    return df[["SCADA_KEY", "TAG"]].fillna("")

# ===================== Carga dumps locales =====================

def _base_dir(out_root: Path, empresa: str) -> Path:
    return out_root / "out" / empresa.upper() / "HSH"

def _load_lookup_full_keys(base_dir: Path) -> Set[str]:
    path = base_dir / "lookup_table.csv"
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path, dtype=str, usecols=["Key", "key"], encoding="utf-8").fillna("")
    except Exception:
        try:
            df = pd.read_csv(path, dtype=str, encoding="utf-8").fillna("")
        except Exception:
            return set()
    col = None
    for c in df.columns:
        if c.strip().lower() == "key":
            col = c
            break
    if not col:
        return set()
    keys: Set[str] = set()
    for raw in df[col].tolist():
        k = _norm_key(raw)
        if k:
            keys.add(k)
    return keys

def _load_lookup_base_keys(base_dir: Path) -> Set[str]:
    full = _load_lookup_full_keys(base_dir)
    bases: Set[str] = set()
    for k in full:
        base = k.split(".", 1)[0]
        if base:
            bases.add(base)
    return bases

def _derive_uid3(uid: str, uid3: str) -> str:
    u3 = _norm_key(uid3)
    if u3:
        return u3
    parts = [p for p in (uid or "").split("/") if p]
    return _norm_key(parts[-1]) if parts else ""

def _load_groups_map(base_dir: Path) -> Dict[str, Dict[Tuple[str, str], str]]:
    """base_key -> {(cpid, uid) -> PointName}"""
    path = base_dir / "groups.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str, encoding="utf-8").fillna("")
    except Exception:
        return {}
    cols = {c.upper(): c for c in df.columns}
    if not {"CPID", "UID"}.issubset(set(cols.keys())):
        return {}
    groups: Dict[str, Dict[Tuple[str, str], str]] = defaultdict(dict)
    for _, row in df.iterrows():
        uid = _norm_str(row.get(cols.get("UID", "UID"), ""))
        cpid = _norm_str(row.get(cols.get("CPID", "CPID"), ""))
        if not uid or not cpid:
            continue
        base_key = _derive_uid3(uid, _norm_str(row.get(cols.get("UID3", "UID3"), "")))
        if not base_key:
            continue
        point = _norm_str(row.get(cols.get("POINTNAME", "PointName"), ""))
        combo = (cpid, uid)
        if combo not in groups[base_key]:
            groups[base_key][combo] = point
    return groups

# ===================== Mongo helpers =====================

def _collect_full_keys_from_mongo(coll, base_keys: Set[str]) -> Tuple[Set[str], Dict[str, str]]:
    """
    Devuelve un par (set_normalizado, map_normalizado->original) con todas las keys exactas cuyo prefijo
    coincide con alguna base_key.
    """
    normalized: Set[str] = set()
    original_map: Dict[str, str] = {}
    if not base_keys:
        return normalized, original_map
    # Buscar por prefijo para enumerar exactas
    ors = [{"key": {"$regex": f"^{re.escape(b)}"}} for b in sorted(base_keys)]
    try:
        for doc in coll.find({"$or": ors}, {"key": 1}):
            raw = (doc.get("key") or "").strip()
            norm = _norm_key(raw)
            if norm:
                normalized.add(norm)
                original_map.setdefault(norm, raw)
    except Exception:
        pass
    return normalized, original_map

def _enumerate_and_optionally_delete(empresa: str, server: str, base_keys: Set[str], apply: bool, logger=None, logger_console=None) -> Tuple[int, int, Set[str], Set[str]]:
    """
    Enumera keys por prefijo y, si apply=True, borra por lista exacta ($in).
    Retorna: (deleted_count, remaining_count, full_seen_before, full_seen_after)
    """
    client = tunnel = None
    cert_path = ca_path = None
    full_before: Set[str] = set()
    full_after: Set[str] = set()
    deleted = 0
    remaining = 0
    try:
        client, tunnel, cert_path, ca_path = conexion_hsh(empresa, server, logger, logger_console)  # type: ignore
        coll = client[_target_db(empresa)]["lookup_tables"]
        if not base_keys:
            return 0, 0, set(), set()
        # 1) Enumerar exactas por prefijo:
        full_before_norm, full_before_map = _collect_full_keys_from_mongo(coll, base_keys)
        if not apply:
            # Solo validar: decir qué borraríamos
            if full_before_norm:
                print(f"LOOKUP_WOULD_DELETE:{empresa}:{','.join(sorted(full_before_norm))}")
            return 0, 0, full_before_norm, set()
        # 2) Borrar por igualdad exacta:
        if full_before_norm:
            print(f"DELETE_KEYS:{empresa}:{','.join(sorted(full_before_norm))}")
            delete_targets = [full_before_map[k] for k in full_before_norm if k in full_before_map]
            result = coll.delete_many({"key": {"$in": delete_targets}})
            deleted = int(result.deleted_count or 0)
        # 3) Contar remanente por prefijo:
        ors = [{"key": {"$regex": f"^{re.escape(b)}"}} for b in sorted(base_keys)]
        remaining = int(coll.count_documents({"$or": ors}) or 0)
        if remaining > 0:
            # enumerar remanentes exactos
            full_after_norm, _ = _collect_full_keys_from_mongo(coll, base_keys)
        else:
            full_after_norm = set()
        return deleted, remaining, full_before_norm, full_after_norm
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass
        try:
            if tunnel and getattr(tunnel, "is_alive", lambda: False)():
                tunnel.stop()
        except Exception:
            pass
        for temp in (cert_path, ca_path):
            if temp and os.path.exists(temp):
                try:
                    os.remove(temp)
                except Exception:
                    pass

# ===================== CSV Delete/Purge =====================

RowInfo = Tuple[str, str]  # (cpid, uid)

def _write_commands(file_path: Path, action: str, rows: Iterable[RowInfo], timestamp: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["header", "2", timestamp])
        for cpid, uid in rows:
            if not cpid or not uid:
                continue
            w.writerow([action, cpid, uid, "CONTINUOUS", "", ""])

def _short_list(items: Iterable[str], limit: int = 6) -> str:
    data = sorted({it for it in items if it})
    if not data:
        return ""
    if len(data) <= limit:
        return ", ".join(data)
    head = ", ".join(data[:limit])
    return f"{head}, (+{len(data) - limit})"

# ===================== CLI =====================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("empresa", type=str, help="Empresa (ITCO, TRA, REPS, REPP)")
    p.add_argument("--input", required=True, help="Excel con columnas SCADA_KEY y TAG (TAG opcional)")
    p.add_argument("--server", default=None, help="Servidor donde aplicar (obligatorio con --apply)")
    p.add_argument("--server-respaldo", default=None, help="Servidor del respaldo (opcional)")
    p.add_argument("--respaldo", default=None, help="Empresa respaldo (informativo; no se procesa aquí)")
    p.add_argument("--apply", action="store_true", help="Borrar en Mongo además de validar")
    return p.parse_args()

# ===================== Main =====================

def main() -> int:
    args = _parse_args()
    empresa = _norm_key(args.empresa)
    if not empresa:
        raise ValueError("Debes indicar una empresa válida.")
    if args.apply and not args.server:
        raise ValueError("Cuando uses --apply debes indicar --server.")

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {input_path}")

    # 1) Leer input -> sacar BASE KEYS en orden
    df_input = _read_input(input_path)
    ordered_bases: List[str] = []
    seen: Set[str] = set()
    for raw in df_input["SCADA_KEY"].tolist():
        k = _norm_key(raw)
        if not k:
            continue
        base = k.split(".", 1)[0]
        if base and base not in seen:
            seen.add(base)
            ordered_bases.append(base)
    if not ordered_bases:
        raise ValueError("El archivo de entrada no contiene SCADA_KEY válidos.")

    out_root = Path(output_root())
    timestamp = str(int(time.time() * 1000))
    eliminar_dir = out_root / "out" / "eliminar_tag"

    # 2) Cargar dumps locales SOLO de esta empresa
    base_dir = _base_dir(out_root, empresa)
    lookup_full = _load_lookup_full_keys(base_dir)
    lookup_bases = _load_lookup_base_keys(base_dir)
    groups_map = _load_groups_map(base_dir)

    warnings: List[str] = []
    if not lookup_bases:
        warnings.append("lookup_table.csv no disponible o vacío.")
    if not groups_map:
        warnings.append("groups.csv no disponible o vacío.")

    # 3) Cruces locales para generar Delete/Purge y marcar faltantes
    records: Set[RowInfo] = set()
    group_variants: Set[str] = set()
    missing_lookup: Set[str] = set()
    missing_groups: Set[str] = set()
    lookup_match_bases: Set[str] = set()
    group_details: Dict[str, List[Dict[str, str]]] = {}
    missing_global: List[str] = []

    for base in ordered_bases:
        found_any = False
        if base in lookup_bases:
            lookup_match_bases.add(base)
        else:
            missing_lookup.add(base)

        rows = groups_map.get(base)
        if rows:
            found_any = True
            detail_list: List[Dict[str, str]] = []
            for (cpid, uid), point in rows.items():
                suf = _norm_key(point)
                if not suf:
                    tail = (uid.split('/')[-1] if uid else '').strip()
                    suf = _norm_key(tail) if tail and tail != base else ''
                variant = f"{base}.{suf}" if suf else base
                group_variants.add(variant)
                records.add((cpid, uid))
                detail_list.append({"cpid": cpid, "uid": uid, "point": point, "variant": variant})
            detail_list.sort(key=lambda d: (d.get('cpid', ''), d.get('uid', '')))
            group_details[base] = detail_list
        else:
            missing_groups.add(base)

        if not found_any:
            missing_global.append(base)

    for base in ordered_bases:
        status = 'PRESENT' if base in lookup_match_bases else 'ABSENT'
        print(f"LOOKUP_STATUS:{empresa}:{base}:{status}")
        details = group_details.get(base, [])
        print(f"GROUP_MATCH:{empresa}:{base}:{json.dumps(details, ensure_ascii=False)}")

    # 4) Si --apply: eliminar en Mongo por lista exacta
    logger = logger_console = None
    if args.apply and Logger is not None:
        log_dir = out_root / 'log'
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            logger, logger_console = Logger.initlog(str(log_dir / f"eliminar_lookup_{empresa.lower()}.log"))
        except Exception:
            logger = logger_console = None

    deleted = remaining = 0
    full_seen_before: Set[str] = set()
    full_seen_after: Set[str] = set()

    base_keys_for_mongo: Set[str] = set(lookup_match_bases)
    for gv in group_variants:
        base_keys_for_mongo.add(gv.split('.', 1)[0])
    base_keys_for_mongo.update(ordered_bases)

    if args.apply:
        if conexion_hsh is None:
            raise RuntimeError('conexion_hsh no disponible; no se puede aplicar eliminacion.')
        deleted, remaining, full_seen_before, full_seen_after = _enumerate_and_optionally_delete(
            empresa, args.server, base_keys_for_mongo, True, logger, logger_console
        )
        print(f"LOOKUP_DELETE:{empresa}:{deleted}")
        print(f"LOOKUP_REMAINING:{empresa}:{remaining}")
        removed_keys = sorted(set(full_seen_before) - set(full_seen_after))
        still_keys = sorted(set(full_seen_after))
        if removed_keys:
            print(f"LOOKUP_REMOVED:{empresa}:{','.join(removed_keys)}")
        if still_keys:
            print(f"LOOKUP_STILL:{empresa}:{','.join(still_keys)}")
    else:
        if conexion_hsh is not None and args.server:
            _, _, full_seen_before, _ = _enumerate_and_optionally_delete(
                empresa, args.server, base_keys_for_mongo, False, logger, logger_console
            )
        if full_seen_before:
            print(f"LOOKUP_WOULD_DELETE:{empresa}:{','.join(sorted(full_seen_before))}")

    emitted: Set[str] = set()
    emitted.update(full_seen_before)
    emitted.update(full_seen_after)
    emitted.update(k for k in group_variants if k)
    if lookup_full:
        for base in ordered_bases:
            for fk in lookup_full:
                if fk.startswith(base):
                    emitted.add(fk)

    delete_paths: List[Path] = []
    purge_paths: List[Path] = []

    if args.apply:
        if not emitted:
            emitted.update(ordered_bases)
        print(f"DELETE_KEYS:{empresa}:{','.join(sorted(emitted))}")
        if records:
            delete_path = eliminar_dir / f"{empresa}_delete_UIDs.csv"
            purge_path = eliminar_dir / f"{empresa}_purge_UIDs.csv"
            rows_sorted = sorted(records, key=lambda it: (it[0], it[1]))
            _write_commands(delete_path, 'Delete', rows_sorted, timestamp)
            _write_commands(purge_path, 'Purge', rows_sorted, timestamp)
            delete_paths.append(delete_path)
            purge_paths.append(purge_path)
            print(f"DELETE_FILE:{delete_path}")
            print(f"PURGE_FILE:{purge_path}")

    # 7) Resumenes
    summary: List[str] = []
    if warnings:
        for w in warnings:
            summary.append(f"{empresa}: {w}")
    if missing_lookup:
        summary.append(f"{empresa}: claves sin coincidencia en lookup_table.csv -> {_short_list(missing_lookup)}")
    if missing_groups:
        summary.append(f"{empresa}: claves sin coincidencia en groups.csv -> {_short_list(missing_groups)}")
    if missing_global:
        summary.append(f"Claves sin coincidencias en los dumps HSH: {_short_list(missing_global)}")
    if args.apply and not delete_paths and not purge_paths:
        summary.append("No se generaron archivos Delete/Purge (sin coincidencias en groups.csv).")
    _emit_summary(summary)

    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR:{exc}", file=sys.stderr)
        raise SystemExit(1)
