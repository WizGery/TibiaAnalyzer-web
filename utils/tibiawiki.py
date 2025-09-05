from __future__ import annotations

# Standard lib
import base64
import re
from typing import Optional, Tuple
from urllib.parse import quote

# Third-party
import requests
import streamlit as st

WIKI_BASE = "https://tibia.fandom.com/wiki/"
HTTP_TIMEOUT = 12
HTTP_HEADERS = {
    "User-Agent": "TibiaAnalyzer/1.0 (+https://github.com/WizGery/TibiaAnalyzer-web)"
}

def _title_from_name_original(name: str) -> str:
    """
    Lógica original: usar el nombre tal cual, reemplazando espacios por '_'
    y conservando los guiones '-'. No forzamos mayúsculas/minúsculas.

    Ejemplos:
      "Frost Flower Asura" -> "Frost_Flower_Asura"
      "Hellspawn"          -> "Hellspawn"
      "Two-Headed Turtle"  -> "Two-Headed_Turtle"
    """
    raw = (name or "").strip()
    # colapsar espacios múltiples
    raw = re.sub(r"\s+", " ", raw)
    # reemplazar espacios por underscores y dejar '-' intacto
    return raw.replace(" ", "_")

def _build_page_url(monster_name: str) -> str:
    title = _title_from_name_original(monster_name)
    # No codificar '-' ni '_' para respetar la forma esperada de Fandom
    return f"{WIKI_BASE}{quote(title, safe='-_')}"

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_monster_icon_url(monster_name: str) -> Optional[str]:
    """
    Devuelve la URL absoluta del GIF del monstruo en TibiaWiki (si se encuentra).
    """
    page_url = _build_page_url(monster_name)
    try:
        resp = requests.get(page_url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200 or not resp.text:
            return None

        # Buscar primer .gif (sprites de monstruos en infobox suelen ser GIF)
        m = re.search(r'<img[^>]+src="([^"]+?\.gif)"', resp.text, re.IGNORECASE)
        if not m:
            return None

        src = m.group(1)
        if src.startswith("//"):
            return "https:" + src
        if src.startswith("/"):
            return "https://tibia.fandom.com" + src
        return src

    except requests.RequestException:
        return None

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_monster_icon_data_uri(monster_name: str) -> Optional[str]:
    """
    Descarga el GIF y devuelve un Data URI (base64) listo para usar en <img src="...">.
    """
    img_url = get_monster_icon_url(monster_name)
    if not img_url:
        return None
    try:
        r = requests.get(img_url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        if r.status_code != 200 or not r.content:
            return None
        b64 = base64.b64encode(r.content).decode("ascii")
        return f"data:image/gif;base64,{b64}"
    except requests.RequestException:
        return None

def get_monster_icon_pair(monster_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Devuelve (data_uri, src_url) donde:
      - data_uri es el GIF en base64 para <img src="...">
      - src_url es la URL directa del GIF (no la del artículo)
    """
    src_url = get_monster_icon_url(monster_name)
    if not src_url:
        return None, None
    data_uri = get_monster_icon_data_uri(monster_name)
    return data_uri, src_url
