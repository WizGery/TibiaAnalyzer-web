from __future__ import annotations

"""
Orquesta el backup/restore de datos.

- export_backup_bytes()  -> devuelve (bytes, filename)
- import_backup_replace_processed(raw_bytes) -> reemplaza TODO el store con el backup

Notas:
- Por compatibilidad, si existe una implementación previa en `ta_core.repository`
  para exportar, la reutilizamos (y normalizamos el tipo de retorno).
- El import reemplaza TODO el store y limpia hashes.
"""

from typing import Tuple, Any, Dict, List, Optional
import json
from datetime import datetime

# Dependencias de persistencia mínimas
from ta_core.repository import load_store, save_store

# Reutilizamos export si todavía existe en repository (compatibilidad)
try:
    from ta_core.repository import export_backup_bytes as _repo_export_backup_bytes  # type: ignore[attr-defined]
except Exception:  # ImportError u otros: no lo tomamos como error fatal
    _repo_export_backup_bytes = None  # type: ignore[assignment]


def _normalize_export_result(out: Any) -> Tuple[bytes, str]:
    """
    Acepta bytes o (bytes, filename) y devuelve una tupla normalizada.
    """
    if isinstance(out, tuple) and len(out) == 2 and isinstance(out[0], (bytes, bytearray)) and isinstance(out[1], str):
        return bytes(out[0]), out[1]
    if isinstance(out, (bytes, bytearray)):
        return bytes(out), "tibia_analyzer_backup.json"
    raise ValueError("Unexpected export result type; expected bytes or (bytes, filename).")


def _fallback_export_bytes() -> Tuple[bytes, str]:
    """
    Exportación de respaldo si no existe la función en repository.
    Serializa el store tal cual a JSON.
    """
    data: List[Dict[str, Any]] = load_store()
    payload: Dict[str, Any] = {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "store": data,
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return raw, "tibia_analyzer_backup.json"


def export_backup_bytes() -> Tuple[bytes, str]:
    """
    Exporta el backup completo de la aplicación.
    Devuelve: (bytes, nombre_de_archivo)
    """
    # Si hay una exportación ya implementada en repository, la usamos.
    if _repo_export_backup_bytes is not None:
        out = _repo_export_backup_bytes()  # type: ignore[misc]
        return _normalize_export_result(out)

    # Si no, usamos el fallback local.
    return _fallback_export_bytes()


def import_backup_replace_processed(raw_bytes: bytes) -> None:
    """
    Importa un backup y **reemplaza** por completo el store actual.

    Formatos admitidos:
      - Dict con clave "store": {"store": [...]}  (nuevo/fallback)
      - Lista directa de registros: [...]         (compatibilidad)

    Lanza ValueError/JSONDecodeError si el contenido no es válido.
    """
    text = raw_bytes.decode("utf-8")
    obj: Any = json.loads(text)

    # Detectar forma
    data: Optional[List[Dict[str, Any]]] = None

    if isinstance(obj, dict) and "store" in obj:
        maybe_list = obj.get("store")
        if not isinstance(maybe_list, list):
            raise ValueError("Backup 'store' must be a list.")
        data = maybe_list  # type: ignore[assignment]
    elif isinstance(obj, list):
        data = obj  # type: ignore[assignment]
    else:
        raise ValueError("Backup has unexpected shape. Expected object with 'store' or a list.")

    # Reemplazar all el store
    save_store(data if data is not None else [])
