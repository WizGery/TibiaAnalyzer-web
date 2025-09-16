from __future__ import annotations

# ---------------- Standard library ----------------
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
import re
import time
import os
import json

# ---------------- Third-party ----------------
import requests
import streamlit as st

# ---------------- Internal ----------------
# (ya no usamos load_store/save_store para chars)

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
API_BASE = "https://api.tibiadata.com/v3"          # API pública (cuando esté disponible)
CODE_TTL_MINUTES = 15                               # vigencia del código
UA = {"User-Agent": "TibiaAnalyzer-Web/1.0"}        # user agent simple para requests
USER_FILE = os.path.join("data", "user_data.json")  # persistencia propia de usuarios

# ---------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class OwnedChar:
    name: str
    world: str
    vocation: str
    level: int
    verified_at: str  # ISO8601


# ---------------------------------------------------------------------
# Helpers de persistencia en data/user_data.json
#   ⚠️ Persistimos SOLO el NOMBRE del personaje por usuario.
# ---------------------------------------------------------------------
def _load_user_data() -> Dict[str, Any]:
    """Carga todo el JSON de data/user_data.json. Devuelve {} si no existe o está corrupto."""
    try:
        if not os.path.exists(USER_FILE):
            return {}
        with open(USER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_user_data(data: Dict[str, Any]) -> None:
    """Guarda el JSON en user_data.json con escritura atómica."""
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    tmp_path = USER_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, USER_FILE)


def _load_all_characters() -> Dict[str, List[Dict[str, str]]]:
    """
    Devuelve el mapa user_id -> list[{ "name": str }].
    Hace compactación silenciosa si detecta formato antiguo con campos extra.
    """
    data = _load_user_data()
    chars = data.get("characters", {})
    if not isinstance(chars, dict):
        return {}

    changed = False
    for uid, items in list(chars.items()):
        if not isinstance(items, list):
            chars[uid] = []
            changed = True
            continue
        new_items: List[Dict[str, str]] = []
        for it in items:
            if isinstance(it, dict):
                nm = str(it.get("name", "")).strip()
            else:
                nm = str(it or "").strip()
            if nm:
                new_items.append({"name": nm})
        if new_items != items:
            chars[uid] = new_items
            changed = True

    if changed:
        data["characters"] = chars
        _save_user_data(data)

    return chars


def _save_all_characters(char_map: Dict[str, List[Dict[str, str]]]) -> None:
    """Guarda el mapa user_id -> list[{name}] en user_data.json."""
    data = _load_user_data()
    data["characters"] = char_map
    _save_user_data(data)


# ---------------------------------------------------------------------
# Códigos temporales (en session_state)
# ---------------------------------------------------------------------
def _code_key(user_id: str, char_name: str) -> str:
    return f"verify_code::{user_id}::{char_name.strip().lower()}"


def generate_or_get_code(user_id: str, char_name: str) -> Tuple[str, datetime]:
    """
    Devuelve (code, expires_at_utc). Si existe y no ha caducado, reutiliza.
    Se almacena SOLO en session_state (no persistente).
    """
    cleaned = (char_name or "").strip()
    if not cleaned:
        raise ValueError("Character name is required.")

    key = _code_key(user_id, cleaned)
    now = datetime.now(timezone.utc)

    entry = st.session_state.get(key)
    if entry:
        code: str = entry["code"]
        exp: datetime = entry["exp"]
        if now < exp:
            return code, exp

    short = re.sub(r"[^A-Za-z0-9]", "", cleaned)[:6].upper()
    ts = int(now.timestamp())
    code = f"TA-{short}-{ts}"

    exp = now + timedelta(minutes=CODE_TTL_MINUTES)
    st.session_state[key] = {"code": code, "exp": exp}
    return code, exp


# ---------------------------------------------------------------------
# Caché en memoria de proceso (Streamlit) para SNAPSHOTS + TIMESTAMPS
#   - Estructura:
#     {
#       user_id: {
#         char_lower: {
#           "snapshot": {"world": str, "vocation": str, "level": int, "verified_at": str},
#           "level_ts": ISO8601,
#           "world_ts": ISO8601
#         }
#       }
#     }
#   - Vive por proceso; se reinicia al reiniciar el servidor.
# ---------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _char_store() -> Dict[str, Dict[str, Dict[str, Any]]]:
    return {}


def _get_entry(user_id: str, char_name: str) -> Dict[str, Any]:
    store = _char_store()
    u = store.setdefault(user_id, {})
    return u.setdefault((char_name or "").strip().lower(), {})


def _get_snapshot(user_id: str, char_name: str) -> Dict[str, Any]:
    e = _get_entry(user_id, char_name)
    snap = e.get("snapshot") or {}
    # valores seguros por defecto
    return {
        "world": str(snap.get("world") or "—"),
        "vocation": str(snap.get("vocation") or "—"),
        "level": int(snap.get("level") or 0),
        "verified_at": str(snap.get("verified_at") or ""),
    }


def _set_snapshot(user_id: str, char_name: str, world: str, vocation: str, level: int, verified_at: str = "") -> None:
    e = _get_entry(user_id, char_name)
    e["snapshot"] = {
        "world": str(world or "—"),
        "vocation": str(vocation or "—"),
        "level": int(level or 0),
        "verified_at": str(verified_at or ""),
    }


def _get_ts(user_id: str, char_name: str, key: str) -> Optional[datetime]:
    e = _get_entry(user_id, char_name)
    iso = e.get(key)
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None


def _touch_ts(user_id: str, char_name: str, key: str) -> None:
    e = _get_entry(user_id, char_name)
    e[key] = datetime.now(timezone.utc).isoformat()


def _need_level_refresh(user_id: str, char_name: str) -> bool:
    last = _get_ts(user_id, char_name, "level_ts")
    if last is None:
        return True
    return (datetime.now(timezone.utc) - last) >= timedelta(minutes=1)


def _need_world_refresh(user_id: str, char_name: str) -> bool:
    last = _get_ts(user_id, char_name, "world_ts")
    if last is None:
        return True
    return (datetime.now(timezone.utc) - last) >= timedelta(days=30)


# ---------------------------------------------------------------------
# Persistencia de "propiedad" (solo nombre) en user_data.json
# ---------------------------------------------------------------------
def add_owned_character(user_id: str, char: OwnedChar) -> None:
    """
    Añade un personaje persistiendo únicamente su nombre.
    Evita duplicados por nombre (case-insensitive).
    Además, inicializa snapshot en caché si venía en 'char'.
    """
    char_map = _load_all_characters()
    items = char_map.get(user_id, [])
    if not any((c.get("name") or "").lower() == char.name.lower() for c in items):
        items.append({"name": char.name})
    char_map[user_id] = items
    _save_all_characters(char_map)

    # Semilla de caché con lo que tengamos (si lo hay)
    _set_snapshot(user_id, char.name, char.world, char.vocation, char.level, char.verified_at)
    _touch_ts(user_id, char.name, "level_ts")
    _touch_ts(user_id, char.name, "world_ts")


def list_owned_characters(user_id: str) -> List[OwnedChar]:
    """
    Devuelve lista de OwnedChar usando el snapshot en caché si existe
    (muestra datos reales entre reruns), y valores seguros si no hay snapshot.
    """
    items = _load_all_characters().get(user_id, [])  # default: []
    out: List[OwnedChar] = []
    for c in items:
        name = str(c.get("name", "")).strip()
        if not name:
            continue
        snap = _get_snapshot(user_id, name)
        out.append(OwnedChar(
            name=name,
            world=snap["world"],
            vocation=snap["vocation"],
            level=snap["level"],
            verified_at=snap["verified_at"],
        ))
    return out


def remove_owned_character(user_id: str, char_name: str) -> bool:
    """Elimina un personaje 'propiedad' del usuario y borra su entrada en caché."""
    char_map = _load_all_characters()
    items = char_map.get(user_id, [])
    before = len(items)
    items = [c for c in items if (c.get("name", "").lower() != (char_name or "").strip().lower())]
    char_map[user_id] = items
    if len(items) != before:
        _save_all_characters(char_map)
        # limpiar caché
        u = _char_store().get(user_id, {})
        u.pop((char_name or "").strip().lower(), None)
        return True
    return False


# ---------------------------------------------------------------------
# Integración con API pública (TibiaData v3) - parser tolerante
# ---------------------------------------------------------------------
def fetch_character_from_api(char_name: str) -> Optional[Dict[str, Any]]:
    """
    Devuelve el dict del personaje desde TibiaData v3 o None si no se pudo obtener.
    Estructuras conocidas:
      v3: {"characters": {"character": {...}}}
      (algunos mirrors): {"character": {...}}
    """
    url = f"{API_BASE}/character/{requests.utils.quote(char_name)}"
    try:
        resp = requests.get(url, timeout=10, headers=UA)
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    try:
        data = resp.json() or {}
    except ValueError:
        return None

    root = data.get("characters") or data.get("character") or {}
    if isinstance(root, dict) and isinstance(root.get("character"), dict):
        return root["character"]
    if isinstance(root, dict):
        return root
    return None


# ---------------------------------------------------------------------
# Fallbacks mínimos a tibia.com
# ---------------------------------------------------------------------
def _fetch_comment_from_tibia_com(char_name: str) -> Optional[str]:
    """
    Lee el 'Comment:' del bloque 'Character Information' en tibia.com.
    Devuelve None si no se pudo obtener la página; '' si no hay comment.
    """
    url = "https://www.tibia.com/community/"
    params = {"name": char_name}
    try:
        resp = requests.get(url, params=params, timeout=12, headers=UA)
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    html = resp.text
    html = re.sub(r"\s+", " ", html)  # normaliza espacios para facilitar regex

    m_block = re.search(r"Character Information.*?</table>", html, re.IGNORECASE)
    if not m_block:
        return None
    block = m_block.group(0)

    m_comment = re.search(r">Comment:</td>\s*<td[^>]*>(.*?)</td>", block, re.IGNORECASE)
    if not m_comment:
        return ""

    raw = m_comment.group(1)
    # Quita tags HTML y decodifica entidades básicas
    raw = re.sub(r"<[^>]+>", "", raw).strip()
    raw = (raw.replace("&nbsp;", " ")
               .replace("&amp;", "&")
               .replace("&lt;", "<")
               .replace("&gt;", ">"))
    return raw


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_api_cached(char_name: str) -> Optional[Dict[str, Any]]:
    """Wrapper cacheado de la API pública para aliviar reruns."""
    return fetch_character_from_api(char_name)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_tibiacom_details(char_name: str) -> Optional[Dict[str, Any]]:
    """
    Devuelve dict con {name, level, world, vocation} scrapeando la tabla 'Character Information'.
    """
    url = "https://www.tibia.com/community/"
    params = {"name": char_name}
    try:
        resp = requests.get(url, params=params, timeout=12, headers=UA)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    html = resp.text
    html = re.sub(r"\s+", " ", html)

    m_block = re.search(r"Character Information.*?</table>", html, re.IGNORECASE)
    if not m_block:
        return None
    block = m_block.group(0)

    def _cell(label: str) -> Optional[str]:
        m = re.search(fr">{re.escape(label)}:</td>\s*<td[^>]*>(.*?)</td>", block, re.IGNORECASE)
        if not m:
            return None
        raw = m.group(1)
        raw = re.sub(r"<[^>]+>", "", raw).strip()
        raw = (raw.replace("&nbsp;", " ").replace("&amp;", "&")
                   .replace("&lt;", "<").replace("&gt;", ">"))
        return raw

    name = _cell("Name")
    level_s = _cell("Level") or "0"
    world = _cell("World") or "—"
    vocation = _cell("Vocation") or "—"

    lvl_match = re.search(r"\d+", level_s)
    level = int(lvl_match.group(0)) if lvl_match else 0

    return {"name": name or char_name, "level": level, "world": world, "vocation": vocation}


def _fetch_comment_from_api(char_name: str, retries: int = 2, delay: float = 0.7) -> Optional[str]:
    """
    Intenta obtener el 'comment' desde TibiaData v3 con pequeños reintentos.
    Devuelve None si la llamada falla, '' si no hay comment.
    """
    for _ in range(retries):
        info = fetch_character_from_api(char_name)
        if info is not None:
            return str(info.get("comment") or info.get("commentary") or "")
        time.sleep(delay)
    return None


def _details_via_api_or_scrape(char_name: str) -> Optional[Dict[str, Any]]:
    """Intenta API; si falta algo o no responde, cae a tibia.com."""
    api = _fetch_api_cached(char_name)
    if isinstance(api, dict) and api:
        name = api.get("name")
        level = api.get("level")
        world = api.get("world")
        vocation = api.get("vocation")
        have_all = (name is not None) and (level is not None) and (world is not None) and (vocation is not None)
        if have_all:
            return {"name": str(name), "level": int(level), "world": str(world), "vocation": str(vocation)}
    # fallback
    return _fetch_tibiacom_details(char_name)


# ---------------------------------------------------------------------
# Verificación del código
# ---------------------------------------------------------------------
def verify_character_code(user_id: str, char_name: str) -> bool:
    """
    Verifica que el comentario del personaje contiene el código vigente.
    Si verifica, añade el personaje (solo nombre) y sembramos caché de snapshot.
    """
    cleaned = (char_name or "").strip()
    if not cleaned:
        return False

    key = _code_key(user_id, cleaned)
    entry = st.session_state.get(key)
    if not entry:
        return False

    code: str = entry["code"]
    exp: datetime = entry["exp"]
    if not code or datetime.now(timezone.utc) >= exp:
        return False

    # 1) Intento por API
    comment = _fetch_comment_from_api(cleaned)
    if comment is not None:
        st.session_state["_last_verify_comment"] = comment
        if code in comment:
            info = fetch_character_from_api(cleaned)
            world = str((info.get("world") if info else "—") or "—")
            vocation = str((info.get("vocation") if info else "—") or "—")
            level = int((info.get("level") if info else 0) or 0)
            verified_at = datetime.now(timezone.utc).isoformat()

            # persistimos solo nombre y cacheamos snapshot
            oc = OwnedChar(
                name=str((info.get("name") if info else cleaned) or cleaned),
                world=world,
                vocation=vocation,
                level=level,
                verified_at=verified_at,
            )
            add_owned_character(user_id, oc)
            return True

    # 2) Fallback tibia.com
    comment = _fetch_comment_from_tibia_com(cleaned)
    st.session_state["_last_verify_comment"] = comment or ""
    if comment is None or code not in comment:
        return False

    info = fetch_character_from_api(cleaned)
    world = str((info.get("world") if info else "—") or "—")
    vocation = str((info.get("vocation") if info else "—") or "—")
    level = int((info.get("level") if info else 0) or 0)
    verified_at = datetime.now(timezone.utc).isoformat()

    oc = OwnedChar(
        name=str((info.get("name") if info else cleaned) or cleaned),
        world=world,
        vocation=vocation,
        level=level,
        verified_at=verified_at,
    )
    add_owned_character(user_id, oc)
    return True


# ---------------------------------------------------------------------
# Refresco de personajes usando CACHÉ (snapshot + timestamps)
#   - level: cada 1 minuto (según level_ts)
#   - world: cada 30 días (según world_ts)
#   - Si no toca refrescar, se usa el snapshot en caché.
#   - Si toca, se consulta y se actualiza snapshot + timestamps en caché.
#   - No se persisten datos dinámicos en disco.
# ---------------------------------------------------------------------
def refresh_owned_characters(user_id: str) -> List[OwnedChar]:
    """
    Devuelve un snapshot consistente para la UI.
    Si hay datos en caché recientes, se muestran incluso tras un rerun.
    """
    char_map = _load_all_characters()
    items = char_map.get(user_id, [])
    out: List[OwnedChar] = []

    for c in items:
        name = str(c.get("name", "")).strip()
        if not name:
            continue

        need_level = _need_level_refresh(user_id, name)
        need_world = _need_world_refresh(user_id, name)

        details: Optional[Dict[str, Any]] = None
        if need_level or need_world:
            details = _details_via_api_or_scrape(name) or {}
            # actualizar snapshot y timestamps si tenemos info
            if "level" in details:
                _touch_ts(user_id, name, "level_ts")
            if "world" in details:
                _touch_ts(user_id, name, "world_ts")
            if details:
                _set_snapshot(
                    user_id,
                    name,
                    world=str(details.get("world") or "—"),
                    vocation=str(details.get("vocation") or "—"),
                    level=int(details.get("level") or 0),
                    verified_at="",  # opcional
                )

        # construir desde snapshot de caché (o seguros)
        snap = _get_snapshot(user_id, name)
        out.append(OwnedChar(
            name=name,
            world=snap["world"],
            vocation=snap["vocation"],
            level=snap["level"],
            verified_at=snap["verified_at"],
        ))

    return out
