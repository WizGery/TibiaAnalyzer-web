
from __future__ import annotations
from typing import List, Dict, Tuple, Any, Iterable
import json

from ..repository import load_store, save_store

# Importar aquí para evitar ciclos entre repository <-> normalizer
from ..normalizer import normalize_records


def _key_from_store_item(orig: Dict[str, Any]) -> Tuple[str, str, int]:
    """
    Clave estable para identificar hunts tanto en 'store' original como en normalizados:
    (session_start, session_end, xp_gain_int)
    Acepta claves en inglés o las usadas en el backup original.
    """
    o_start = str(orig.get("Session start", orig.get("session_start", "")))
    o_end = str(orig.get("Session end", orig.get("session_end", "")))

    xo_raw = str(orig.get("XP Gain", orig.get("xp_gain", 0)))
    # limpiar separadores
    xo_raw = xo_raw.replace(".", "").replace(",", "")
    try:
        xo = int(float(xo_raw))
    except Exception:
        xo = 0
    return (o_start, o_end, xo)


def _key_from_norm_row(row: Dict[str, Any]) -> Tuple[str, str, int]:
    """
    Igual que _key_from_store_item pero desde una fila normalizada (dict-like).
    """
    s_start = str(row.get("session_start", ""))
    s_end = str(row.get("session_end", ""))
    xg = row.get("xp_gain", 0)
    try:
        xg_i = int(float(str(xg).replace(".", "").replace(",", "")))
    except Exception:
        xg_i = 0
    return (s_start, s_end, xg_i)


def import_backup_replace_processed(backup_bytes: bytes) -> None:
    """
    Reemplaza los hunts PROCESADOS por los del backup, manteniendo los PENDIENTES actuales.
    - Carga store actual
    - Normaliza para detectar pendientes actuales
    - Normaliza backup para reconstruir 'procesados' a partir de su fuente original
    - Construye un nuevo store: (pendientes actuales) + (procesados del backup)
    """
    try:
        obj = json.loads(backup_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        obj = {}

    backup_store: List[Dict] = obj.get("store", []) or []
    # hashes del backup, si los usas, puedes tomarlos de obj.get("hashes", [])
    # pero la persistencia dependerá de cómo guardes en save_store

    # 1) Estado actual
    current_store: List[Dict] = load_store()
    cur_norm, cur_pending = normalize_records(current_store)

    # Conjunto de claves de pendientes actuales (para conservarlos tal cual)
    pending_keys = set(_key_from_norm_row(r) for _, r in cur_pending.iterrows())

    # 2) Normalizar backup para mapear claves -> registro original
    b_norm, _ = normalize_records(backup_store)

    # Construir diccionario clave -> item_original_del_backup
    backup_by_key: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    for _, row in b_norm.iterrows():
        src = row.get("source_raw")
        if isinstance(src, dict):
            orig = src
        else:
            # Si no viene la fuente, intentamos reconstruir con lo que haya
            orig = {
                "Session start": row.get("session_start", ""),
                "Session end": row.get("session_end", ""),
                "XP Gain": row.get("xp_gain", 0),
                "Vocation": row.get("vocation"),
                "Mode": row.get("mode"),
                "Zona": row.get("zona"),
                "Level": row.get("level_bucket"),
            }
        backup_by_key[_key_from_norm_row(row)] = orig

    # 3) Construir nuevo store:
    #    - conservar PENDIENTES actuales (del store original)
    #    - añadir PROCESADOS del backup
    #    Para conservar los pendientes, buscamos en el store actual por clave.
    current_by_key: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    for it in current_store:
        current_by_key[_key_from_store_item(it)] = it

    new_store: List[Dict] = []

    # 3.a) añadir pendientes actuales (tal cual estaban en current_store)
    for k in pending_keys:
        if k in current_by_key:
            new_store.append(current_by_key[k])

    # 3.b) añadir procesados del backup (todas las claves del backup)
    for k, it in backup_by_key.items():
        # si la clave es pendiente actual, ya está añadida como pendiente; no duplicar
        if k in pending_keys:
            continue
        new_store.append(it)

    # 4) Guardar
    save_store(new_store)
