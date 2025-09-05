# ta_core/repository.py
import json
import os
import hashlib
from typing import List, Dict, Tuple

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
    # Deduplicar por si entran repetidos
    hashes = list(dict.fromkeys(hashes))
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
    - Devuelve (ok_count, fail_count).
    """
    ensure_data_dirs()
    rows = load_store()
    hashes = set(load_hashes())

    ok = 0
    fail = 0
    # Caminos (hashes) nuevos detectados en esta subida (para sellar owner después si procede)
    new_hashes_this_batch: List[str] = []

    for f in files:
        try:
            data = f.read()
            sha = hashlib.sha256(data).hexdigest()
            if sha in hashes:
                # Duplicado → lo saltamos
                continue
            # Parse JSON (puede ser objeto o lista de objetos)
            obj = json.loads(data.decode("utf-8"))
            if isinstance(obj, dict):
                item = obj
                # Asegurar flags mínimos
                if "has_all_meta" not in item:
                    item["has_all_meta"] = False
                # NUEVO: owner vacío por defecto (se rellenará en la capa superior)
                item.setdefault("owner_user_id", None)
                rows.append(item)
                ok += 1
            elif isinstance(obj, list):
                for item in obj:
                    if not isinstance(item, dict):
                        continue
                    if "has_all_meta" not in item:
                        item["has_all_meta"] = False
                    item.setdefault("owner_user_id", None)  # NUEVO
                    rows.append(item)
                    ok += 1
            else:
                fail += 1
                continue

            hashes.add(sha)
            new_hashes_this_batch.append(sha)
        except Exception:
            fail += 1

    save_store(rows)
    save_hashes(list(hashes))

    # Devolvemos (ok, fail). El sellado efectivo del owner lo hará la página Upload
    # tras conocer el usuario actual. Aquí solo garantizamos el campo presente (None).
    return ok, fail


def dedupe_info() -> Dict:
    """
    Devuelve información resumida para debug tras una subida/import.
    """
    rows = load_store()
    hashes = load_hashes()
    hashes_count = len(hashes)
    return {
        "store_rows": len(rows),
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


# -----------------------
# Conteos por usuario (total finalizado y pendientes)
# -----------------------
def get_user_counts() -> Dict[str, Dict[str, int]]:
    """
    Devuelve { user_id: {"total": X, "pending": Y} }.

    - 'total' cuenta SOLO hunts con has_all_meta=True (finalizadas).
    - 'pending' cuenta hunts con has_all_meta=False.
    - Si un registro no tiene owner_user_id, se agrupa en 'unknown'.
    """
    rows = load_store()
    by_user: Dict[str, Dict[str, int]] = {}
    for rec in rows:
        uid = rec.get("owner_user_id") or "unknown"
        d = by_user.setdefault(uid, {"total": 0, "pending": 0})
        if rec.get("has_all_meta", False):
            d["total"] += 1
        else:
            d["pending"] += 1
    return by_user
