"""Valida un Excel de nuevas tags HSH contra los dumps locales de SCADA/HSH."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, NamedTuple
from bson import Int64  

import pandas as pd
from pymongo.errors import BulkWriteError

try:
    from utils.paths import output_root, config_path
except Exception:  # pragma: no cover - soporte ejecucion directa
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
    from utils.paths import output_root, config_path  # type: ignore

try:
    from scripts import _Logger as Logger  # type: ignore
    from scripts.functions import conexion_hsh  # type: ignore
    from scripts.import_base import company_prefixes, related_server_candidates  # type: ignore
except Exception:
    try:
        import _Logger as Logger  # type: ignore
        from functions import conexion_hsh  # type: ignore
        from import_base import company_prefixes, related_server_candidates  # type: ignore
    except Exception:
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
        import _Logger as Logger  # type: ignore
        from functions import conexion_hsh  # type: ignore
        from import_base import company_prefixes, related_server_candidates  # type: ignore


ALLOWED_TAG_CHARS = set("-_")
LOOKUP_TABLE_NAME = "Tabla1"


BACKUP_RELATIONS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "REPS": ("REPP", ("rep1", "rep2")),
    "REPP": ("REPS", ("rep1", "rep2")),
    "ITCO": ("TRA", ("tra1", "tra2")),
    "TRA": ("ITCO", ("itco1", "itco2")),
}

# ===================== Helpers SCADA dual-side =====================

def _db_label(source: Optional[str]) -> Optional[str]:
    if source == "STATUS":
        return "10_4 STATUS"
    if source == "ANALOG":
        return "10_5 ANALOG"
    return None

def _read_scada_side(empresa: Optional[str],
                     key: str,
                     scada_info_by_empresa: Dict[str, Dict[str, Dict[str, object]]]
                     ) -> Tuple[str, Optional[str], Optional[int], Optional[int], Optional[int]]:
    """
    Devuelve (estado, source, archive_value, lsb, second)
    estado = 'OFF' | 'ON' | 'NO_ENCONTRADA'
    """
    emp = _norm_key(empresa) if empresa else None
    entry = (scada_info_by_empresa.get(emp, {}) if emp else {}).get(key)
    if not entry:
        return "NO_ENCONTRADA", None, None, None, None

    source = entry.get("source")
    ag = entry.get("value")
    lsb = entry.get("lsb")
    second = entry.get("second")

    if source == "STATUS":
        estado = "OFF" if (lsb in (0, None)) else "ON"
    elif source == "ANALOG":
        estado = "OFF" if (lsb in (0, None) and second in (0, None)) else "ON"
    else:
        estado = "NO_ENCONTRADA"

    return estado, source, ag, lsb, second


def _primera_causa_desc(empresa: str, source: Optional[str], ag: Optional[int], lsb: Optional[int], second: Optional[int]) -> str:
    if source is None:
        return f"Descartada: key no encontrada en {empresa}"
    db = _db_label(source)
    if source == "STATUS":
        return f"Descartada: bit de envío ON en {empresa} (DB={db}, archive_group={ag}, bit0={lsb})"
    else:
        return f"Descartada: bits de envío ON en {empresa} (DB={db}, archive_group={ag}, bit0={lsb}, bit1={second})"


def _related_company(empresa: str) -> Optional[str]:
    relation = BACKUP_RELATIONS.get(_norm_key(empresa))
    return relation[0] if relation else None


def _extract_server_prefix(server: str, prefixes: Optional[Iterable[str]] = None) -> Optional[Tuple[str, str]]:
    targets = list(prefixes or [])
    if targets:
        for prefix in targets:
            if prefix and prefix in server:
                suffix = server.split(prefix, 1)[1]
                return prefix, suffix
        return None
    # fallback: detectar por palabras clave
    for token in ("sca", "qds"):
        if token in server:
            idx = server.index(token)
            return server[:idx], server[idx:]
    return None


def _company_server_candidates(server: str, empresa: str) -> List[str]:
    prefixes = company_prefixes(_norm_key(empresa)) if 'company_prefixes' in globals() else ()
    if not prefixes:
        return [server]
    extracted = _extract_server_prefix(server, prefixes)
    if not extracted:
        return [server]
    _, suffix = extracted
    generated = [f"{prefix}{suffix}" for prefix in prefixes if prefix]
    ordered = [server, *generated]
    return list(dict.fromkeys(ordered))


def _related_servers(server: str, empresa: str) -> List[str]:
    try:
        candidates = related_server_candidates(server, empresa) if 'related_server_candidates' in globals() else []
    except Exception:
        candidates = []
    if candidates:
        return [c for c in dict.fromkeys(candidates) if c]
    if not candidates:
        # fallback al mapa local
        relation = BACKUP_RELATIONS.get(_norm_key(empresa))
        if not relation:
            return [server]
        _, target_prefixes = relation
        extracted = _extract_server_prefix(server)
        if extracted:
            src_prefix, suffix = extracted
            candidates = [f"{target}{suffix}" for target in target_prefixes if target]
            if src_prefix and src_prefix not in target_prefixes:
                candidates.insert(0, server)
        else:
            candidates = [server]
    return [c for c in dict.fromkeys(candidates) if c]


def _target_db(empresa: str) -> str:
    mapping = {
        "REPS": "PI_REPS",
        "REPP": "PI_REPP",
        "ITCO": "PI_ITCO",
        "TRA": "PI_TRA",
    }
    return mapping.get(empresa.upper(), empresa)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("empresa", type=str, help="Nombre de la empresa principal")
    parser.add_argument("--input", required=True, help="Archivo Excel de entrada")
    parser.add_argument("--respaldo", default=None, help="Empresa respaldo (opcional)")
    parser.add_argument("--diccionario", default=config_path("diccionario_tags.json"),
                        help="Ruta al diccionario de terminaciones")
    parser.add_argument("--apply", action="store_true", help="Inserta los tags validados en la base de datos HSH")
    parser.add_argument("--server", default=None, help="Servidor base (obligatorio cuando se usa --apply)")
    parser.add_argument("--skip-backup-insert", action="store_true",
                        help="No inserta en la empresa respaldo (usado cuando se ejecuta por separado)")
    return parser.parse_args()


def _clean_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _norm_key(value: str) -> str:
    return _clean_str(value).upper()


def _collect_lookup_variants(value: str) -> Iterable[str]:
    value = value.strip().upper()
    if not value:
        return []
    variants = {value}
    if "." in value:
        variants.add(value.split(".", 1)[0])
    return variants


def _candidate_base_dirs(empresa: str, out_root_path: Optional[str]) -> List[Path]:
    candidates: List[Path] = []
    cwd = Path(os.getcwd()).resolve()
    candidates.append(cwd / "out" / empresa)
    if out_root_path:
        candidates.append(Path(out_root_path).resolve() / "out" / empresa)

    unique: List[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            real = candidate.resolve()
        except Exception:
            real = candidate
        if real not in seen:
            seen.add(real)
            unique.append(real)
    return unique


def _read_csv_lenient(path: Path) -> Optional[pd.DataFrame]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return pd.read_csv(fh, dtype=str)
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1", errors="ignore") as fh:
                return pd.read_csv(fh, dtype=str)
        except Exception as exc:
            print(f"[WARN] No se pudo leer {path} (latin-1): {exc}")
            return None
    except Exception as exc:
        print(f"[WARN] No se pudo leer {path}: {exc}")
        return None


def _load_suffix_dict(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el diccionario de terminaciones: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        raise ValueError(f"No se pudo leer el diccionario {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"El diccionario {path} no tiene el formato esperado")
    result: Dict[str, List[str]] = {}
    for key, value in data.items():
        if not isinstance(value, list):
            raise ValueError(f"Sufijos invalidos para clave {key!r} en {path}")
        result[str(key).strip()] = [str(v).strip() for v in value]
    return result


class HSHData(NamedTuple):
    all_keys: set[str]
    all_tags: set[str]
    lookup_keys: set[str]
    lookup_tags: set[str]
    groups_tags: set[str]
    groups_key_counts: Counter[str]
    missing: List[str]


def _load_hsh_sets(out_root_path: Optional[str], empresas: Iterable[str]) -> HSHData:
    all_keys: set[str] = set()
    all_tags: set[str] = set()
    lookup_keys: set[str] = set()
    lookup_tags: set[str] = set()
    groups_tags: set[str] = set()
    groups_key_counts: Counter[str] = Counter()
    missing: List[str] = []
    seen_files: set[Path] = set()

    tag_columns = {"value", "linkattributevalue", "tag", "tagname", "pointname"}

    for empresa in empresas:
        found_for_empresa = False
        for base_dir in _candidate_base_dirs(empresa, out_root_path):
            hsh_dir = base_dir / "HSH"
            print(f"[INFO] Buscando HSH para {empresa} en: {hsh_dir}")
            if not hsh_dir.is_dir():
                continue
            for fname in ("lookup_table.csv", "groups.csv"):
                path = hsh_dir / fname
                if not path.exists():
                    print(f"[WARN] Archivo HSH no encontrado: {path}")
                    continue
                real = path.resolve()
                if real in seen_files:
                    continue
                seen_files.add(real)
                df = _read_csv_lenient(path)
                if df is None:
                    continue
                found_for_empresa = True

                lowered = {column.strip().lower(): column for column in df.columns}
                for column in df.columns:
                    series = df[column].dropna()
                    if series.empty:
                        continue
                    lowered_name = column.strip().lower()
                    if lowered_name in tag_columns:
                        for raw_value in series.astype(str):
                            tag = _clean_str(raw_value)
                            if not tag:
                                continue
                            all_tags.add(tag)
                            if fname == "lookup_table.csv":
                                lookup_tags.add(tag)
                            elif fname == "groups.csv":
                                groups_tags.add(tag)
                    for raw_value in series.astype(str):
                        for variant in _collect_lookup_variants(raw_value):
                            if variant:
                                all_keys.add(variant)

                if fname == "lookup_table.csv" and "key" in lowered:
                    col = lowered["key"]
                    for raw_key in df[col].dropna().astype(str):
                        norm = _norm_key(raw_key)
                        if norm:
                            lookup_keys.add(norm)
                if fname == "groups.csv" and "uid3" in lowered:
                    col = lowered["uid3"]
                    for raw_key in df[col].dropna().astype(str):
                        base = _norm_key(raw_key)
                        if base:
                            groups_key_counts[base] += 1
                            all_keys.add(base)
        if not found_for_empresa:
            missing.append(f"HSH ({empresa})")

    return HSHData(all_keys, all_tags, lookup_keys, lookup_tags, groups_tags, groups_key_counts, missing)


def _load_scada_data(out_root_path: Optional[str], empresas: Iterable[str]
    ) -> Tuple[Dict[str, set[str]], Dict[str, Dict[str, Dict[str, object]]], List[str]]:
    """
    Carga los dumps SCADA 10_4 (STATUS) y 10_5 (ANALOG) por empresa.

    Returns:
        - keys_by_empresa: { EMPRESA -> set(keys y variantes) }
        - info_by_empresa: {
              EMPRESA -> {
                  KEY -> {
                      "value": archive_group (int|None),
                      "lsb":   bit0 (0/1|None),
                      "second":bit1 (0/1|None solo ANALOG),
                      "source":"STATUS"|"ANALOG"
                  }
              }
          }
        - missing: lista de advertencias
    """
    keys_by_empresa: Dict[str, set[str]] = {}
    info_by_empresa: Dict[str, Dict[str, Dict[str, object]]] = {}
    missing: List[str] = []
    seen_files: set[Path] = set()

    def _parse_archive_value(raw: object) -> Optional[int]:
        try:
            if raw is None:
                return None
            s = str(raw).strip()
            if not s:
                return None
            return int(float(s))
        except Exception:
            return None

    def _store(empresa_norm: str, raw_key: str, archive_value: Optional[int], source: str) -> None:
        if not raw_key:
            return
        normalized = _norm_key(raw_key)
        variants = set(_collect_lookup_variants(normalized)) or {normalized}

        info_emp = info_by_empresa.setdefault(empresa_norm, {})
        keys_emp = keys_by_empresa.setdefault(empresa_norm, set())

        for variant in variants:
            existing = info_emp.get(variant)
            # Prioridad a ANALOG frente a STATUS, pero SOLO dentro de la MISMA empresa
            if existing and existing.get("source") == "ANALOG" and source != "ANALOG":
                continue
            lsb = (archive_value & 1) if archive_value is not None else None
            second = ((archive_value >> 1) & 1) if (archive_value is not None and source == "ANALOG") else None
            info_emp[variant] = {
                "value": archive_value,
                "lsb": lsb,
                "second": second,
                "source": source,
            }
            keys_emp.add(variant)

    for empresa in empresas:
        empresa_norm = _norm_key(empresa)
        found_for_empresa = False
        for base_dir in _candidate_base_dirs(empresa_norm, out_root_path):
            scada_dir = base_dir / "SCADA"
            print(f"[INFO] Buscando SCADA para {empresa_norm} en: {scada_dir}")
            if not scada_dir.is_dir():
                continue
            csv_files = sorted(p for p in scada_dir.glob("*.csv") if p.name.startswith(("10_4", "10_5")))
            if not csv_files:
                print(f"[WARN] No se encontraron archivos 10_4/10_5 en {scada_dir}")
                continue
            for path_csv in csv_files:
                real = path_csv.resolve()
                if real in seen_files:
                    continue
                print(f"[INFO] Leyendo SCADA: {path_csv}")
                seen_files.add(real)
                df = _read_csv_lenient(path_csv)
                if df is None:
                    continue
                found_for_empresa = True

                key_column = None
                archive_column = None
                for column in df.columns:
                    cname = column.strip().lower()
                    if cname == "key":
                        key_column = column
                    if cname == "archive_group":
                        archive_column = column

                source = "ANALOG" if path_csv.name.startswith("10_5") else "STATUS"

                if key_column:
                    key_series = df[key_column].astype(str)
                    archive_series = df[archive_column] if archive_column in df.columns else None
                    for idx, raw_key in enumerate(key_series):
                        archive_value = _parse_archive_value(archive_series.iloc[idx]) if archive_series is not None else None
                        _store(empresa_norm, raw_key, archive_value, source)

                # Recolecta variantes vistas (opcional)
                for column in df.columns:
                    if column == key_column:
                        continue
                    series = df[column].dropna()
                    if series.empty:
                        continue
                    for raw_value in series.astype(str):
                        for variant in _collect_lookup_variants(raw_value):
                            if variant:
                                keys_by_empresa.setdefault(empresa_norm, set()).add(variant)

        if not found_for_empresa:
            missing.append(f"SCADA 10_4/10_5 ({empresa_norm})")

    return keys_by_empresa, info_by_empresa, missing



def _validate_tag_name(raw_tag: str) -> Tuple[Optional[str], List[str], List[str]]:
    errors: List[str] = []
    generated_tags: List[str] = []
    normalized = _clean_str(raw_tag)
    if not normalized:
        errors.append("TAG sin contenido")
        return None, generated_tags, errors

    parts = normalized.split(":")
    if len(parts) != 5:
        errors.append("El TAG debe tener 5 partes separadas por ':'")
        return None, generated_tags, errors

    cleaned_parts: List[str] = []
    for part in parts:
        clean = part.strip()
        if not clean:
            errors.append("Alguna parte del TAG quedo vacia")
            return None, generated_tags, errors
        for ch in clean:
            if ch.isspace():
                errors.append(f"El caracter '{ch}' no esta permitido en el TAG; evita espacios")
                return None, generated_tags, errors
            if not (ch.isalnum() or ch in ALLOWED_TAG_CHARS):
                errors.append(f"Caracter no permitido '{ch}' en el TAG. Usa solo letras, numeros, '-' o '_'")
                return None, generated_tags, errors
        cleaned_parts.append(clean)

    return ":".join(cleaned_parts), cleaned_parts, errors


def _build_results(df: pd.DataFrame,
                   hsh_data: HSHData,
                   scada_info_by_emp: Dict[str, Dict[str, Dict[str, object]]],
                   suffix_dict: Dict[str, List[str]],
                   args: argparse.Namespace) -> pd.DataFrame:
    STAGE_SYNTAX = 1
    STAGE_INPUT = 2
    STAGE_SCADA = 3
    STAGE_SUFFIX = 4
    STAGE_HSH = 5

    counter_keys = Counter(_norm_key(k) for k in df["SCADA_KEY"])
    counter_tags_input = Counter(_clean_str(t) for t in df["TAG"])

    estados: List[str] = []
    primera_causa: List[str] = []
    detalle_full: List[str] = []
    archive_sources: List[Optional[str]] = []
    archive_values: List[Optional[int]] = []
    archive_lsb: List[Optional[int]] = []
    archive_second: List[Optional[int]] = []
    tags_generados_col: List[str] = []
    generated_pairs_col: List[List[Tuple[str, str]]] = []

    generated_tag_pool: set[str] = set()
    generated_key_pool: set[str] = set()

    analog_forbidden = {'.State'}
    analog_required = {'.Value'}
    status_forbidden = {'.Value', '.Estimated'}
    status_required = {'.State'}

    for _, row in df.iterrows():
        error_records: List[Tuple[int, str]] = []
        warning_records: List[Tuple[int, str]] = []
        generated_tags: List[str] = []
        generated_keys: List[str] = []

        raw_key = row.get("SCADA_KEY", "")
        normalized_key = _norm_key(raw_key)
        raw_tag = row.get("TAG", "")
        cleaned_tag = _clean_str(raw_tag)

        def add_error(stage: int, message: str) -> None:
            error_records.append((stage, message))

        def add_warning(stage: int, message: str) -> None:
            warning_records.append((stage, message))

        # Stage 1: Sintaxis del TAG
        normalized_tag, tag_parts, tag_errors = _validate_tag_name(raw_tag)
        for err in tag_errors:
            add_error(STAGE_SYNTAX, err)

        # Stage 2: Validaciones de entrada
        if not normalized_key:
            add_error(STAGE_INPUT, "SCADA_KEY sin contenido")
        if cleaned_tag and counter_tags_input[cleaned_tag] > 1:
            add_error(STAGE_INPUT, "TAG repetido en el archivo")

        empresa_principal = args.empresa.strip().upper() if hasattr(args, "empresa") else "<PRINCIPAL>"
        empresa_respaldo = (args.respaldo.strip().upper() if getattr(args, "respaldo", None) else None)

        # === NUEVO: consulta por empresa ===
        estado_p, src_p, ag_p, lsb_p, second_p = _read_scada_side(empresa_principal, normalized_key, scada_info_by_emp)
        estado_b, src_b, ag_b, lsb_b, second_b = _read_scada_side(empresa_respaldo, normalized_key, scada_info_by_emp) if empresa_respaldo else ("NO_ENCONTRADA", None, None, None, None)

        # Log informativo
        print(f"[SCADA] {normalized_key}: {empresa_principal}={estado_p}, {empresa_respaldo or 'RESPALDO'}={estado_b}")

        # Guardar valores básicos (compatibilidad columnas actuales)
        archive_sources.append(src_p)
        archive_values.append(ag_p)
        archive_lsb.append(lsb_p)
        archive_second.append(second_p)

        # Stage 3: Reglas de descarte por SCADA
        if estado_p != "OFF" or estado_b != "OFF":
            if estado_p != "OFF":
                causa = _primera_causa_desc(empresa_principal, src_p, ag_p, lsb_p, second_p)
            else:
                causa = _primera_causa_desc(empresa_respaldo or "RESPALDO", src_b, ag_b, lsb_b, second_b)
            add_error(STAGE_SCADA, causa)
            print(f"[DESCARTA] {normalized_key} -> {causa}")
        else:
            print(f"[OK SCADA] {normalized_key} -> OFF en ambos lados")

        # Stage 4: Terminaciones/generación
        source = None
        try:
            source = (archive_sources[-1] if archive_sources else None)
        except Exception:
            source = None

        scada_tiene_error = any(stage == STAGE_SCADA for stage, _ in error_records)

        if normalized_tag and normalized_key and (source in ("STATUS", "ANALOG")) and not tag_errors and not scada_tiene_error:
            base_suffix_key = tag_parts[-1]
            suffixes = suffix_dict.get(base_suffix_key)
            if not suffixes:
                add_error(STAGE_SUFFIX, f"No hay terminaciones registradas para '{base_suffix_key}'")
            else:
                suffix_set = set(suffixes)

                if source == "STATUS":
                    if not status_required.issubset(suffix_set):
                        add_error(STAGE_SUFFIX, "Las terminaciones STATUS deben incluir .State")
                    if suffix_set & status_forbidden:
                        add_error(STAGE_SUFFIX, "Las terminaciones STATUS no deben incluir .Value ni .Estimated")

                elif source == "ANALOG":
                    if not analog_required.issubset(suffix_set):
                        add_error(STAGE_SUFFIX, "Las terminaciones ANALOG deben incluir .Value")
                    if suffix_set & analog_forbidden:
                        add_error(STAGE_SUFFIX, "Las terminaciones ANALOG no deben incluir .State")

                generated_tags = [f"{normalized_tag}{suf}" for suf in suffixes]
                generated_keys = [f"{normalized_key}{suf}" for suf in suffixes]

                for tag in generated_tags:
                    if tag in generated_tag_pool:
                        add_error(STAGE_SUFFIX, f"El TAG generado {tag} ya se repite en el archivo")
                for gkey in generated_keys:
                    if gkey in generated_key_pool:
                        add_error(STAGE_SUFFIX, f"La combinacion SCADA_KEY+terminacion {gkey} ya se repite en el archivo")
        elif normalized_tag and normalized_key and not tag_errors and not scada_tiene_error and source not in ("STATUS", "ANALOG"):
            add_error(STAGE_SUFFIX, "No se pudo determinar si la fuente es STATUS o ANALOG para asignar terminaciones")

        # Stage 5: Validaciones HSH (lookup/groups)
        if generated_tags and generated_keys:
            for tag in generated_tags:
                if tag in hsh_data.lookup_tags:
                    add_error(STAGE_HSH, f"El TAG {tag} ya existe en lookup_table.csv")
                elif tag in hsh_data.groups_tags:
                    add_warning(STAGE_HSH, f"El TAG {tag} ya figura en groups.csv")
            for gkey in generated_keys:
                if gkey in hsh_data.lookup_keys:
                    add_error(STAGE_HSH, f"La combinacion SCADA_KEY+terminacion {gkey} ya existe en lookup_table.csv")
            if normalized_key:
                existing = hsh_data.groups_key_counts.get(normalized_key, 0)
                if existing:
                    total_expected = len(suffix_dict.get(tag_parts[-1], [])) if tag_parts else 0
                    if total_expected and existing >= total_expected:
                        add_warning(STAGE_HSH, f"La SCADA_KEY ya esta completa en groups.csv ({existing})")
                    elif total_expected:
                        add_warning(STAGE_HSH, f"La SCADA_KEY tiene {existing} de {total_expected} terminaciones en groups.csv")

        if generated_tags and not any(stage == STAGE_SUFFIX for stage, _ in error_records):
            generated_tag_pool.update(generated_tags)
        if generated_keys and not any(stage == STAGE_SUFFIX for stage, _ in error_records):
            generated_key_pool.update(generated_keys)

        if error_records:
            first_stage = float("inf")
            first_message = ""
            for stage, message in error_records:
                if stage < first_stage:
                    first_stage = stage
                    first_message = message
            estados.append("DESCARTADO")
            primera_causa.append(first_message)
        else:
            estados.append("LISTO")
            primera_causa.append("Aprobado")

        if not error_records and generated_tags and generated_keys:
            pairs_list = list(zip(generated_keys, generated_tags))
            tags_generados_col.append("\n".join(f"{gk},{gt}" for gk, gt in pairs_list))
            generated_pairs_col.append(pairs_list)
        else:
            tags_generados_col.append("")
            generated_pairs_col.append([])

        detail_msgs: List[str] = []
        for _, stage, message in sorted(((idx, stage, message) for idx, (stage, message) in enumerate(error_records)), key=lambda item: (item[1], item[0])):
            detail_msgs.append(message)
        for _, stage, message in sorted(((idx, stage, message) for idx, (stage, message) in enumerate(warning_records)), key=lambda item: (item[1], item[0])):
            detail_msgs.append(message)
        detalle_full.append("; ".join(dict.fromkeys(detail_msgs)))

    result = df.copy()
    result["SCADA_KEY"] = result["SCADA_KEY"].map(_norm_key)
    result["TAG"] = result["TAG"].map(_clean_str)
    result["Estado"] = estados
    result["PrimeraCausa"] = primera_causa
    result["DetalleCompleto"] = detalle_full
    result["ArchiveSource"] = archive_sources
    result["ArchiveGroupValue"] = archive_values
    result["ArchiveLSB"] = archive_lsb
    result["ArchiveSecondLSB"] = archive_second
    result["TagsGenerados"] = tags_generados_col
    result["GeneratedPairs"] = generated_pairs_col
    return result



def _output_dir() -> Path:
    base = Path(output_root()).resolve() / "out" / "crear_tag"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _save_report(df: pd.DataFrame) -> Path:
    report_dir = _output_dir()
    report_path = report_dir / "reporte_crear_tag.xlsx"

    reporte_df = df.copy()
    for col in ["TagsGenerados", "PrimeraCausa"]:
        if col not in reporte_df:
            reporte_df[col] = ""
    reporte_df.loc[reporte_df["Estado"] == "LISTO", "PrimeraCausa"] = reporte_df.loc[
        reporte_df["Estado"] == "LISTO", "PrimeraCausa"
    ].replace("", "Aprobado")
    reporte_df = reporte_df[["SCADA_KEY", "TAG", "Estado", "PrimeraCausa", "TagsGenerados"]]

    detalle_cols = [
        "SCADA_KEY",
        "TAG",
        "Estado",
        "PrimeraCausa",
        "DetalleCompleto",
        "ArchiveSource",
        "ArchiveGroupValue",
        "ArchiveLSB",
        "ArchiveSecondLSB",
        "TagsGenerados",
        "Empresa_Principal", "DB_Principal", "AG_Value_Principal",
        "Empresa_Respaldo", "DB_Respaldo", "AG_Value_Respaldo"
    ]
    detalle_df = df.copy()
    for col in detalle_cols:
        if col not in detalle_df:
            detalle_df[col] = ""
    detalle_df = detalle_df[detalle_cols]

    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        reporte_df.to_excel(writer, sheet_name="Reporte", index=False)
        detalle_df.to_excel(writer, sheet_name="Detalle", index=False)

    return report_path


def _create_tags_stub(listos: pd.DataFrame) -> None:
    _ = listos


def _write_query_file(pairs: List[Tuple[str, str]]) -> Path:
    query_path = _output_dir() / "query_crear_tag.js"
    with query_path.open("w", encoding="utf-8") as fh:
        if not pairs:
            fh.write("// No hay tags listos para generar la query.\n")
            return query_path

        fh.write("db.lookup_tables.insertMany([\n")
        for idx, (key, value) in enumerate(pairs):
            comma = "," if idx < len(pairs) - 1 else ""
            fh.write("   {\n")
            fh.write("       deleted: false,\n")
            fh.write(f"       key: \"{key}\",\n")
            fh.write(f"       table_name: \"{LOOKUP_TABLE_NAME}\",\n")
            fh.write("       last_change_us: NumberLong(new Date().getTime()),\n")  # <-- sin comillas
            fh.write(f"       value: \"{value}\"\n")
            fh.write(f"   }}{comma}\n")
        fh.write("]);\n")
    return query_path

def _insert_pairs(empresa: str, server: str, pairs: List[Tuple[str, str]], skip_backup: bool = False) -> Tuple[int, Dict[str, int]]:
    if not pairs:
        print("APPLY_SKIPPED:No hay tags listos para insertar")
        return 0, {}

    log_dir = Path(output_root()).resolve() / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "crear_tag_hsh.log"
    logger, logger_console = Logger.initlog(str(log_path))

    # === millis o micros? ===
    now_ms = int(time.time() * 1000)
    # Si tu base termina guardando con tres ceros extra (microsegundos):
    USE_MICROSECONDS = True
    now_num = now_ms * 1000 if USE_MICROSECONDS else now_ms

    def _build_docs() -> List[Dict[str, object]]:
        return [
            {
                "deleted": False,
                "key": key,
                "table_name": LOOKUP_TABLE_NAME,
                "last_change_us": Int64(now_num),  # <-- BSON Int64 (NumberLong)
                "value": value,
            }
            for key, value in pairs
        ]

    empresa_norm = _norm_key(empresa)
    targets: List[Tuple[str, List[str]]] = []
    seen_empresas: Dict[str, List[str]] = {}

    def _append_target(emp: Optional[str], srv_candidates: Optional[Iterable[str]]) -> None:
        if not emp or not srv_candidates:
            return
        emp_norm = _norm_key(emp)
        if not emp_norm:
            return
        candidates = [str(s).strip() for s in srv_candidates if str(s).strip()]
        if not candidates:
            return
        if emp_norm in seen_empresas:
            # combinar candidatos adicionales evitando duplicados
            existing = seen_empresas[emp_norm]
            for cand in candidates:
                if cand not in existing:
                    existing.append(cand)
        else:
            seen_empresas[emp_norm] = list(dict.fromkeys(candidates))
            targets.append((emp_norm, seen_empresas[emp_norm]))

    primary_candidates = _company_server_candidates(server, empresa_norm)
    _append_target(empresa_norm, primary_candidates)
    if not skip_backup:
        respaldo = _related_company(empresa_norm)
        if respaldo:
            respaldo_servers = _related_servers(server, empresa_norm)
            _append_target(respaldo, respaldo_servers)

    if not targets:
        raise RuntimeError("No se pudo determinar a qué empresas insertar los tags")

    total_inserted = 0
    inserted_by_empresa: Dict[str, int] = {}

    for target_empresa, server_candidates in targets:
        client = tunnel = None
        cert_path = key_path = None
        chosen_server = None
        last_error: Optional[Exception] = None

        Logger.write_log().log_all(
            'info',
            f'[CREAR_TAG] {target_empresa} candidatos: {", ".join(server_candidates)}',
            logger_console,
            logger,
        )

        for target_server in server_candidates:
            try:
                Logger.write_log().log_all(
                    'info',
                    f'[CREAR_TAG] {target_empresa} intentando {target_server}',
                    logger_console,
                    logger,
                )
                client, tunnel, cert_path, key_path = conexion_hsh(target_empresa, target_server, logger, logger_console)
                chosen_server = getattr(client, "_hsh_host", target_server)
                print(f"APPLY_SERVER:{target_empresa}:{chosen_server}")
                ssh_used = getattr(client, "_ssh_host", target_server)
                print(f"APPLY_SSH:{target_empresa}:{ssh_used}")
                Logger.write_log().log_all(
                    'info',
                    f'[CREAR_TAG] {target_empresa} conectado a {chosen_server} (primario)',
                    logger_console,
                    logger,
                )
                break
            except Exception as exc:
                last_error = exc
                print(f"APPLY_WARN:{target_empresa}:Conexion fallida con {target_server}:{exc}")
                Logger.write_log().log_all(
                    'warning',
                    f'[CREAR_TAG] {target_empresa} fallo {target_server}: {exc}',
                    logger_console,
                    logger,
                )
                client = tunnel = None
                cert_path = key_path = None
                continue

        if not chosen_server or client is None:
            raise ConnectionError(
                f"No se pudo establecer conexion primaria para {target_empresa}. "
                f"Intentados: {server_candidates}. Último error: {last_error}"
            )

        try:
            db = client[_target_db(target_empresa)]
            docs = _build_docs()

            inserted_current = 0
            try:
                result = db["lookup_tables"].insert_many(docs, ordered=False)
                inserted_current = len(result.inserted_ids)
            except BulkWriteError as exc:
                inserted_current = exc.details.get("nInserted", 0)
                for err in exc.details.get("writeErrors", []):
                    errmsg = err.get("errmsg") or "Error desconocido"
                    print(f"APPLY_WARN:{target_empresa}:{errmsg}")

            inserted_by_empresa[target_empresa] = inserted_current
            total_inserted += inserted_current
            print(f"APPLY_OK:{target_empresa}:{inserted_current}")
            if inserted_current:
                keys_serialized = ",".join(key for key, _ in pairs)
                tags_serialized = ",".join(value for _, value in pairs)
                print(f"APPLY_KEYS:{target_empresa}:{keys_serialized}")
                print(f"APPLY_TAGS:{target_empresa}:{tags_serialized}")
            Logger.write_log().log_all(
                'info',
                f'[CREAR_TAG] {target_empresa} insertados: {inserted_current}',
                logger_console,
                logger,
            )
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
            for temp in (cert_path, key_path):
                if temp and os.path.exists(temp):
                    try:
                        os.remove(temp)
                    except Exception:
                        pass

    print(f"APPLY_OK_TOTAL:{total_inserted}")
    return total_inserted, inserted_by_empresa



def _write_info_file(empresa: str,
                     total: int,
                     listos: int,
                     descartados: int,
                     pairs: List[Tuple[str, str]],
                     report_path: Path,
                     query_path: Path,
                     insertados: int = 0,
                     insertados_por_empresa: Optional[Dict[str, int]] = None) -> Path:
    info_path = _output_dir() / "informe_crear_tag.txt"
    lines = [
        f"Empresa: {empresa}",
        f"Total filas evaluadas: {total}",
        f"Listos: {listos}",
        f"Descartados: {descartados}",
        f"Reporte Excel: {report_path}",
        f"Archivo de query: {query_path}",
        "",
    ]

    if pairs:
        lines.append("Pairs generados (SCADA_KEY, TAG):")
        for key, value in pairs:
            lines.append(f"- {key}, {value}")
    else:
        lines.append("No se generaron tags nuevos.")

    lines.append("")
    lines.append(f"Total insertados en HSH: {insertados}")
    if insertados_por_empresa:
        lines.append("Detalle inserciones por empresa:")
        for emp, count in insertados_por_empresa.items():
            lines.append(f"- {emp}: {count}")

    info_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return info_path


def main() -> int:
    args = _parse_args()
    empresa = args.empresa.strip()
    respaldo = (args.respaldo or "").strip() or None
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro el archivo de entrada: {input_path}")

    df = _read_input(input_path)

    empresas_consulta: List[str] = [empresa]
    if respaldo and respaldo not in empresas_consulta:
        empresas_consulta.append(respaldo)

    try:
        out_root_path = output_root()
    except Exception:
        out_root_path = None

    print("[INFO] Empresas consideradas:", empresas_consulta)
    print(f"[INFO] Directorio de trabajo actual: {Path(os.getcwd()).resolve()}")
    if out_root_path:
        print(f"[INFO] output_root(): {Path(out_root_path).resolve()}")

    hsh_data = _load_hsh_sets(out_root_path, empresas_consulta)
    missing_hsh = hsh_data.missing

    # === NUEVO: carga SCADA por empresa ===
    scada_keys_by_emp, scada_info_by_emp, missing_scada = _load_scada_data(out_root_path, empresas_consulta)

    suffix_dict = _load_suffix_dict(Path(args.diccionario))

    faltantes = [*missing_hsh, *missing_scada]
    if not hsh_data.all_keys:
        faltantes.append("Dumps HSH no encontrados")

    # Verifica que exista al menos un set de keys en alguna empresa
    if not any(scada_keys_by_emp.values()):
        faltantes.append("Dumps SCADA 10_4/10_5 no encontrados")

    if faltantes:
        raise RuntimeError("No se encontraron datos necesarios: " + ", ".join(faltantes))

    # === SOLO UNA llamada a _build_results ===
    resultados = _build_results(df, hsh_data, scada_info_by_emp, suffix_dict, args)

    report_path = _save_report(resultados.drop(columns=["GeneratedPairs"]))

    total = len(resultados)
    listos_df = resultados[resultados["Estado"] == "LISTO"].copy()
    listos = int(len(listos_df))
    descartados = total - listos

    generated_pairs: List[Tuple[str, str]] = []
    seen_pairs: set[Tuple[str, str]] = set()
    for pairs in listos_df.get("GeneratedPairs", []):
        for key, value in pairs:
            if not key or not value:
                continue
            pair = (key, value)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                generated_pairs.append(pair)

    inserted = 0
    inserted_detail: Dict[str, int] = {}
    if args.apply:
        if not args.server:
            raise ValueError("Cuando uses --apply debes indicar --server")
        inserted, inserted_detail = _insert_pairs(empresa, args.server, generated_pairs, skip_backup=args.skip_backup_insert)

    query_path = _write_query_file(generated_pairs)
    info_path = _write_info_file(
        empresa,
        total,
        listos,
        descartados,
        generated_pairs,
        report_path,
        query_path,
        inserted,
        inserted_detail,
    )

    _create_tags_stub(listos_df)

    print(f"Total registros: {total}")
    print(f"Listos: {listos} | Descartados: {descartados}")
    print(f"REPORT_PATH:{report_path}")
    print(f"INFO_PATH:{info_path}")
    print(f"QUERY_PATH:{query_path}")
    if args.apply:
        print(f"APPLY_RESUMEN: insertados={inserted} solicitados={len(generated_pairs)}")
    return 0


def _read_input(path: Path) -> pd.DataFrame:
    sheet_name = "Crear Tag"
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, usecols=[0, 1], dtype=str)
    except ValueError as exc:
        raise ValueError(f"No se pudo leer la hoja '{sheet_name}' en {path}: {exc}") from exc
    except FileNotFoundError:
        raise
    if df.empty:
        raise ValueError("El archivo de entrada esta vacio")
    original_cols = list(df.columns)
    normalized = [col.strip().upper() for col in original_cols]
    rename_map = {}
    for raw, norm in zip(original_cols, normalized):
        if norm in {"SCADA_KEY", "SCADAKEY", "SCADA KEY"}:
            rename_map[raw] = "SCADA_KEY"
        elif norm in {"TAG", "NOMBRE TAG"}:
            rename_map[raw] = "TAG"
    df = df.rename(columns=rename_map)
    if "SCADA_KEY" not in df.columns or "TAG" not in df.columns:
        raise ValueError("La hoja debe contener columnas 'SCADA_KEY' y 'TAG' en las dos primeras columnas")
    return df[["SCADA_KEY", "TAG"]].fillna("")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
