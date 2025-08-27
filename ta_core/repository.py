import json
import os
import hashlib
from typing import List, Dict, Tuple

from .normalizer import normalize_records  # para separar processed/pending al importar


# -----------------------
# Rutas de datos
# -----------------------
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
STORE_JSONL = os.path.join(DATA_DIR, "store.jsonl")
HASHES_JSON = os.path.join(DATA_DIR, "hashes.json")


# -----------------------
# Utilidades base
# -----------------------
def ensure_data_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(STORE_JSONL):
        open(STORE_JSONL, "a", encoding="utf-8").close()
    if not os.path.exists(HASHES_JSON):
        with open(HASHES_JSON, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)


def load_store() -> List[Dict]:
    ensure_data_dirs()
    rows: List[Dict] = []
    with open(STORE_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def save_store(rows: List[Dict]) -> None:
    ensure_data_dirs()
    with open(STORE_JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_hashes() -> List[str]:
    ensure_data_dirs()
    try:
        with open(HASHES_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_hashes(hashes: List[str]) -> None:
    ensure_data_dirs()
    with open(HASHES_JSON, "w", encoding="utf-8") as f:
        json.dump(list(hashes), f, ensure_ascii=False)


def clear_hashes() -> None:
    """Vacía el fichero data/hashes.json."""
    save_hashes([])


# -----------------------
# Subida de ficheros con desduplicado por hash
# -----------------------
def add_uploaded_files(files) -> Tuple[int, int]:
    """
    Añade JSONs al store aplicando dedupe por hash SHA-256.
    - `files` es la lista de UploadedFile de Streamlit.
    - Devuelve (added_records, skipped_files).
    """
    ensure_data_dirs()
    hashes = set(load_hashes())
    batch_seen = set()

    to_append: List[Dict] = []
    skipped = 0

    for f in files:
        try:
            data = f.getvalue()
        except Exception:
            try:
                # Compat: algunos objetos similares exponen read()
                data = f.read()
            except Exception:
                skipped += 1
                continue

        h = hashlib.sha256(data).hexdigest()
        if h in hashes or h in batch_seen:
            skipped += 1
            continue

        # Parseamos JSON (objeto o array de objetos)
        try:
            obj = json.loads(data.decode("utf-8"))
        except Exception:
            skipped += 1
            continue

        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    to_append.append(item)
        elif isinstance(obj, dict):
            to_append.append(obj)
        else:
            # formato inválido
            skipped += 1
            continue

        # marcamos el hash como visto/guardado
        batch_seen.add(h)
        hashes.add(h)

    added = len(to_append)
    if added:
        store = load_store()
        store.extend(to_append)
        save_store(store)
        save_hashes(list(hashes))

    return added, skipped


def dedupe_info() -> Dict:
    """Devuelve info simple del estado de dedupe/almacenamiento."""
    try:
        store_count = len(load_store())
    except Exception:
        store_count = 0
    try:
        hashes_count = len(load_hashes())
    except Exception:
        hashes_count = 0
    return {
        "store_count": store_count,
        "hashes_count": hashes_count,
        "data_dir": DATA_DIR,
        "store_path": STORE_JSONL,
        "hashes_path": HASHES_JSON,
    }


# -----------------------
# Import/Export de Backup
# -----------------------
def export_backup_bytes() -> Tuple[bytes, str]:
    """
    Devuelve (bytes, filename) de un backup JSON con:
      { "version": 1, "store": [...], "hashes": [...] }
    """
    ensure_data_dirs()
    obj = {
        "version": 1,
        "store": load_store(),
        "hashes": load_hashes(),
    }
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return data, "tibia_analyzer_backup.json"


def _key_from_item(d: Dict) -> Tuple[str, str, int]:
    """Clave estable para identificar una hunt en store/dfs."""
    o_start = str(d.get("Session start", d.get("session_start", "")))
    o_end   = str(d.get("Session end",   d.get("session_end", "")))
    xp_raw  = str(d.get("XP Gain", d.get("xp_gain", 0))).replace(",", "")
    try:
        xp = int(xp_raw)
    except Exception:
        xp = 0
    return (o_start, o_end, xp)


def import_backup_replace_processed(backup_bytes: bytes) -> None:
    """
    Importa un backup JSON (formato export_backup_bytes) y:
      - Reemplaza SOLO los registros PROCESADOS actuales por los PROCESADOS del backup.
      - Mantiene los PENDIENTES actuales tal cual.
      - Sustituye hashes por los del backup (si están).
    """
    ensure_data_dirs()
    obj = json.loads(backup_bytes.decode("utf-8"))
    if not isinstance(obj, dict) or "store" not in obj:
        raise ValueError("Invalid backup: expected an object with 'store'.")

    backup_store: List[Dict] = obj.get("store", [])
    backup_hashes: List[str] = obj.get("hashes", [])

    # Actual
    current_store = load_store()
    cur_norm, cur_pending = normalize_records(current_store)
    pending_keys = set((_key_from_item(r) for _, r in cur_pending.iterrows())) if not cur_pending.empty else set()

    # Del backup, tomamos SOLO procesados
    b_norm, _ = normalize_records(backup_store)
    backup_processed: List[Dict] = []
    if not b_norm.empty:
        # reconstruimos items originales del backup por clave
        backup_by_key: Dict[Tuple[str, str, int], Dict] = {}
        for _, row in b_norm.iterrows():
            src = row.get("source_raw") if isinstance(row.get("source_raw"), dict) else None
            if src is not None:
                backup_by_key[_key_from_item(src)] = src
        # fallback si no había source_raw
        if not backup_by_key:
            for it in backup_store:
                backup_by_key[_key_from_item(it)] = it
        backup_processed = list(backup_by_key.values())

    # Componemos nuevo store: pendientes actuales + procesados del backup
    new_store: List[Dict] = []
    # añade pendientes actuales
    for it in current_store:
        if _key_from_item(it) in pending_keys:
            new_store.append(it)
    # añade procesados del backup
    new_store.extend(backup_processed)

    save_store(new_store)
    # Reemplaza hashes por los del backup (si vienen)
    if isinstance(backup_hashes, list):
        save_hashes(backup_hashes)
