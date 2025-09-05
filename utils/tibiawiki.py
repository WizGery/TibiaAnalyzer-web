# utils/tibiawiki.py
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
    # Algunos hostings bloquean requests sin UA
    "User-Agent": "TibiaAnalyzer/1.0 (+https://github.com/WizGery/TibiaAnalyzer-web)"
}


def _normalize_wiki_title(name: str) -> str:
    """
    Convierte un nombre de monstruo al título de página de TibiaWiki:
    - Reduce espacios múltiples a uno
    - Mantiene los guiones '-'
    - Reemplaza espacios por '_'
    - Capitaliza cada palabra y cada segmento separado por '-'

    Ejemplos:
      "frost flower asura" -> "Frost_Flower_Asura"
      "Two-Headed Turtle"  -> "Two-Headed_Turtle"
      "two-headed turtle"  -> "Two-Headed_Turtle"
    """
    raw = str(name or "").strip()
    raw = raw.replace("_", " ")
    raw = re.sub(r"\s+", " ", raw)

    def cap_token(tok: str) -> str:
        parts = tok.split("-")
        parts = [p[:1].upper() + p[1:].lower() if p else p for p in parts]
        return "-".join(parts)

    tokens = [cap_token(t) for t in raw.split(" ")]
    return "_".join(tokens)


def _build_page_url(monster_name: str) -> str:
    title = _normalize_wiki_title(monster_name)
    # No codificar '-' ni '_' en la URL final
    return f"{WIKI_BASE}{quote(title, safe='-_')}"


@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_monster_icon_url(monster_name: str) -> Optional[str]:
    """
    Devuelve la URL absoluta del GIF del monstruo en TibiaWiki (si se encuentra).
    Cacheada para reducir peticiones.
    """
    page_url = _build_page_url(monster_name)

    try:
        resp = requests.get(page_url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200 or not resp.text:
            return None

        # Heurística: primer .gif del infobox suele ser el icono.
        m = re.search(r'<img[^>]+src="([^"]+?\.gif)"', resp.text, re.IGNORECASE)
        if m:
            src = m.group(1)
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                return "https://tibia.fandom.com" + src
            return src
        return None

    except requests.RequestException:
        return None


@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_monster_icon_data_uri(monster_name: str) -> Optional[str]:
    """
    Descarga el GIF del monstruo y devuelve un Data URI (base64) listo para <img src="...">.
    Cacheada para evitar repetir descargas.
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
    Devuelve (data_uri, src_url) para el icono del monstruo.
    Útil si quieres desempaquetar directamente.
    """
    src_url = get_monster_icon_url(monster_name)
    if not src_url:
        return None, None
    data_uri = get_monster_icon_data_uri(monster_name)
    return data_uri, src_url
