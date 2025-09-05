from __future__ import annotations

# ---------------- Standard library ----------------
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
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
# ---------------------------------------------------------------------
def _load_user_data() -> Dict:
    """Carga all el JSON de data/user_data.json. Devuelve {} si no existe o está corrupto."""
    try:
        if not os.path.exists(USER_FILE):
            return {}
        with open(USER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_user_data(data: Dict) -> None:
    """Guarda all el JSON en user_data.json con escritura atómica."""
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    tmp_path = USER_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, USER_FILE)


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
# Persistencia de "propiedad" del personaje en user_data.json
# ---------------------------------------------------------------------
def _load_all_characters() -> Dict[str, List[Dict]]:
    """Devuelve el mapa user_id -> list[char dict]."""
    data = _load_user_data()
    chars = data.get("characters", {})
    return chars if isinstance(chars, dict) else {}


def _save_all_characters(char_map: Dict[str, List[Dict]]) -> None:
    """Guarda el mapa user_id -> list[char dict] en user_data.json."""
    data = _load_user_data()
    data["characters"] = char_map
    _save_user_data(data)


def add_owned_character(user_id: str, char: OwnedChar) -> None:
    char_map = _load_all_characters()
    items = char_map.get(user_id, [])
    # Evitar duplicados por nombre (case-insensitive)
    if not any((c.get("name") or "").lower() == char.name.lower() for c in items):
        now_iso = datetime.now(timezone.utc).isoformat()
        items.append({
            "name": char.name,
            "world": char.world,
            "vocation": char.vocation,
            "level": int(char.level),
            "verified_at": char.verified_at,
            # timestamps de refresco (sellamos ahora mismo)
            "level_ts": now_iso,
            "world_ts": now_iso,
        })
    char_map[user_id] = items
    _save_all_characters(char_map)


def list_owned_characters(user_id: str) -> List[OwnedChar]:
    items = _load_all_characters().get(user_id, [])  # default: []
    out: List[OwnedChar] = []
    for c in items:
        out.append(OwnedChar(
            name=str(c.get("name", "")),
            world=str(c.get("world", "—")),
            vocation=str(c.get("vocation", "—")),
            level=int(c.get("level", 0) or 0),
            verified_at=str(c.get("verified_at", "")),
        ))
    return out


def remove_owned_character(user_id: str, char_name: str) -> bool:
    """Elimina un personaje 'propiedad' del usuario. Devuelve True si eliminó algo."""
    char_map = _load_all_characters()
    items = char_map.get(user_id, [])
    before = len(items)
    items = [c for c in items if (c.get("name", "").lower() != (char_name or "").strip().lower())]
    char_map[user_id] = items
    if len(items) != before:
        _save_all_characters(char_map)
        return True
    return False


# ---------------------------------------------------------------------
# Integración con API pública (TibiaData v3) - parser tolerante
# ---------------------------------------------------------------------
def fetch_character_from_api(char_name: str) -> Optional[Dict]:
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

    data = resp.json() or {}
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
def _fetch_api_cached(char_name: str) -> Optional[Dict]:
    """Wrapper cacheado de la API pública para aliviar reruns."""
    return fetch_character_from_api(char_name)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_tibiacom_details(char_name: str) -> Optional[Dict]:
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
    Intenta obtener el 'comment' desde TibiaData v3 con pequeños reintentos
    (la API puede estar cacheada o momentáneamente caída).
    Devuelve None si la llamada falla, '' si no hay comment.
    """
    for _ in range(retries):
        info = fetch_character_from_api(char_name)  # ya es tolerante a errores/red
        if info is not None:
            # algunos mirrors usan 'commentary'
            return str(info.get("comment") or info.get("commentary") or "")
        time.sleep(delay)
    return None


def _details_via_api_or_scrape(char_name: str) -> Optional[Dict]:
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
    Orden:
      1) TibiaData v3 (API) con pequeños reintentos
      2) Fallback: tibia.com (scrape mínimo)
    Si verifica, guarda la propiedad y devuelve True.
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
            # Snapshot de datos (si API responde, tomamos de ahí; si no, mínimos)
            info = fetch_character_from_api(cleaned)
            oc = OwnedChar(
                name=str((info.get("name") if info else cleaned) or cleaned),
                world=str((info.get("world") if info else "—") or "—"),
                vocation=str((info.get("vocation") if info else "—") or "—"),
                level=int((info.get("level") if info else 0) or 0),
                verified_at=datetime.now(timezone.utc).isoformat(),
            )
            add_owned_character(user_id, oc)
            return True

    # 2) Fallback tibia.com si API no devolvió comment o no contenía el código
    comment = _fetch_comment_from_tibia_com(cleaned)
    st.session_state["_last_verify_comment"] = comment or ""
    if comment is None:
        return False
    if code not in comment:
        return False

    # Snapshot con best-effort de API (si está disponible)
    info = fetch_character_from_api(cleaned)
    oc = OwnedChar(
        name=str((info.get("name") if info else cleaned) or cleaned),
        world=str((info.get("world") if info else "—") or "—"),
        vocation=str((info.get("vocation") if info else "—") or "—"),
        level=int((info.get("level") if info else 0) or 0),
        verified_at=datetime.now(timezone.utc).isoformat(),
    )
    add_owned_character(user_id, oc)
    return True


# ---------------------------------------------------------------------
# Reglas de refresco por campo
#   - level: cada 1 minuto
#   - world: cada 30 días
#   - name y vocation: estáticos (solo si estaban vacíos)
# ---------------------------------------------------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _touch_ts(d: Dict, key: str) -> None:
    d[key] = _now_utc().isoformat()


def _parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _should_refresh(last_iso: Optional[str], delta: timedelta) -> bool:
    last = _parse_ts(last_iso)
    if last is None:
        return True
    return (_now_utc() - last) >= delta


def refresh_owned_characters(user_id: str) -> List[OwnedChar]:
    """
    Aplica reglas de refresco a cada personaje del usuario:
      - level: cada 1 minuto (o si es 0)
      - world: cada 30 días (o si está vacío/'—')
      - name/vocation: no se tocan salvo que estuvieran vacíos
    Devuelve la lista actualizada (tipada).
    """
    char_map = _load_all_characters()
    items = char_map.get(user_id, [])
    changed = False

    for c in items:
        name = str(c.get("name", "")).strip()
        if not name:
            continue

        cur_level = int(c.get("level", 0) or 0)
        cur_world = str(c.get("world", "") or "").strip()

        need_level = (cur_level == 0) or _should_refresh(c.get("level_ts"), timedelta(minutes=1))
        need_world = (cur_world in {"", "—", "-"}) or _should_refresh(c.get("world_ts"), timedelta(days=30))

        v_raw = str(c.get("vocation", "") or "").strip()
        need_vocation_if_missing = (v_raw == "" or v_raw in {"—", "-"})

        # Solo pedimos detalles si hace falta refrescar algo
        details: Optional[Dict] = None
        if need_level or need_world or need_vocation_if_missing:
            details = _details_via_api_or_scrape(name) or {}

        # vocation: solo si faltaba
        if need_vocation_if_missing and details.get("vocation"):
            c["vocation"] = str(details["vocation"])

        # level: cada minuto (o si era 0)
        if need_level and (details and details.get("level") is not None):
            c["level"] = int(details["level"])
            _touch_ts(c, "level_ts")
            changed = True
        elif c.get("level_ts") is None:
            _touch_ts(c, "level_ts")

        # world: cada 30 días (o si estaba vacío)
        if need_world and (details and details.get("world") is not None):
            c["world"] = str(details["world"])
            _touch_ts(c, "world_ts")
            changed = True
        elif c.get("world_ts") is None:
            _touch_ts(c, "world_ts")

        # aseguramos tipos/valores seguros
        c["level"] = int(c.get("level", 0) or 0)
        c["world"] = str(c.get("world", "—") or "—")
        c["vocation"] = str(c.get("vocation", "—") or "—")

    if changed:
        char_map[user_id] = items
        _save_all_characters(char_map)

    # salida tipada
    out: List[OwnedChar] = []
    for c in items:
        out.append(OwnedChar(
            name=str(c.get("name", "")),
            world=str(c.get("world", "—")),
            vocation=str(c.get("vocation", "—")),
            level=int(c.get("level", 0) or 0),
            verified_at=str(c.get("verified_at", "")),
        ))
    return out
