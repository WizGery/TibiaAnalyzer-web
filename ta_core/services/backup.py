from __future__ import annotations

# ---------------- Standard library ----------------
from typing import Tuple, Dict, Any, Optional, List
from datetime import datetime, timezone
import io
import json
import os
import zipfile

# ---------------- Third-party ----------------
# (none)

# ---------------- Internal ----------------
from ta_core.repository import load_store, save_store, load_hashes, save_hashes  # type: ignore[attr-defined]

# ---------------------------------------------------------------------
# Config / Paths
# ---------------------------------------------------------------------
def _repo_root() -> str:
    # services/ -> ta_core/ -> <repo_root>  (3 niveles)
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

def _data_dir() -> str:
    # Permitir override por variable de entorno si quieres (opcional)
    return os.environ.get("TA_DATA_DIR", os.path.join(_repo_root(), "data"))

def _p_store() -> str: return os.path.join(_data_dir(), "store.jsonl")
def _p_hashes() -> str: return os.path.join(_data_dir(), "hashes.json")
def _p_userdata() -> str: return os.path.join(_data_dir(), "user_data.json")
def _p_monsters() -> str: return os.path.join(_data_dir(), "monster_difficulty.csv")

_FILES: Dict[str, str] = {
    "store.jsonl": _p_store(),
    "hashes.json": _p_hashes(),
    "user_data.json": _p_userdata(),
    "monster_difficulty.csv": _p_monsters(),
}

_BACKUP_NAME = "tibia_analyzer_backup.zip"
_MANIFEST = "manifest.json"
_VERSION = 2  # v2 = multi-file zip with manifest

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _read_file_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None

def _write_file_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def _is_zip(payload: bytes) -> bool:
    return len(payload) >= 4 and payload[:4] == b"PK\x03\x04"

# ---------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------
def export_backup_bytes() -> Tuple[bytes, str]:
    """
    Export all persistent app data in a single zip:
    - store.jsonl
    - hashes.json
    - user_data.json
    - monster_difficulty.csv

    Returns (bytes, filename).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest: Dict[str, Any] = {
            "version": _VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "files": [],
            "data_dir": _data_dir(),
        }
        for arcname, path in _FILES.items():
            content = _read_file_bytes(path)
            if content is None:
                # Si el archivo no existe, incluimos entrada vacía pero lo listamos
                content = b""
            zf.writestr(arcname, content)
            manifest["files"].append({"name": arcname, "size": len(content), "path": path})
        zf.writestr(_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    return buf.getvalue(), _BACKUP_NAME

# ---------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------
def import_backup_replace_processed(raw_bytes: bytes) -> None:
    """
    Restore from a backup.

    Supported formats:
    - v2 zip (this module): manifest.json + listed files (replaces ALL: store, hashes,
      user_data, monster_difficulty).
    - Legacy JSON (list) -> replaces only store.jsonl and clears hashes to avoid duplicates.
    - Legacy JSON (object with "store": [...]) -> idem.
    """
    if _is_zip(raw_bytes):
        with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zf:
            for arcname, path in _FILES.items():
                try:
                    data = zf.read(arcname)
                except KeyError:
                    data = b""
                _write_file_bytes(path, data)

        # Tocar helpers para re-materializar caches si hacen lazy init
        _ = load_store()
        _ = load_hashes()
        return

    # --- Legacy JSON path (pre-v2) ---
    text = raw_bytes.decode("utf-8")
    obj: Any = json.loads(text)

    data: Optional[List[Any]] = None
    if isinstance(obj, dict) and "store" in obj:
        maybe_list = obj.get("store")
        if not isinstance(maybe_list, list):
            raise ValueError("Backup 'store' must be a list.")
        data = maybe_list
    elif isinstance(obj, list):
        data = obj
    else:
        raise ValueError("Unsupported backup format. Expected v2 zip or legacy JSON.")

    # Replace store and reset hashes for legacy imports
    save_store(data if data is not None else [])
    save_hashes([])
