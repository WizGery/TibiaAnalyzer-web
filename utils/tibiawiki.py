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

# ---------- Helpers de título/URL ----------

def _title_from_name_original(name: str) -> str:
    """
    Lógica solicitada:
      - Colapsa espacios múltiples
      - Reemplaza espacios por '_'
      - Conserva '-'
      - No fuerza mayúsculas/minúsculas (usa el nombre tal cual venga)
    """
    raw = (name or "").strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw.replace(" ", "_")

def _build_page_url(monster_name: str) -> str:
    title = _title_from_name_original(monster_name)
    # No codificar '-' ni '_'
    return f"{WIKI_BASE}{quote(title, safe='-_')}"

def _monster_key_variants(monster_name: str) -> list[str]:
    """
    Genera variantes para comparar contra nombres de archivo .gif:
    - Sin espacios/underscores
    - Con/ sin guiones
    - Case-insensitive (se usará en regex con IGNORECASE)
    """
    base = (monster_name or "").strip()
    base = re.sub(r"\s+", " ", base)
    v1 = base                      # "Two-Headed Turtle"
    v2 = base.replace(" ", "_")    # "Two-Headed_Turtle"
    v3 = base.replace("-", " ")    # "Two Headed Turtle"
    v4 = v2.replace("-", "_")      # "Two_Headed_Turtle"
    v5 = base.replace(" ", "")     # "Two-HeadedTurtle"
    v6 = v5.replace("-", "")       # "TwoHeadedTurtle"
    return [v1, v2, v3, v4, v5, v6]

# ---------- Scraping principal ----------

@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_monster_icon_url(monster_name: str) -> Optional[str]:
    """
    Devuelve la URL absoluta del GIF del monstruo en TibiaWiki (si se encuentra),
    priorizando el GIF del infobox y evitando efectos tipo Flame_Effect.gif.
    """
    page_url = _build_page_url(monster_name)
    try:
        resp = requests.get(page_url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200 or not resp.text:
            return None
        html = resp.text

        # 1) Intento: <img ... class="pi-image-thumbnail" ... src="...gif">
        m_infobox = re.search(
            r'<img[^>]+class="[^"]*\bpi-image-thumbnail\b[^"]*"[^>]+src="([^"]+?\.gif[^"]*)"',
            html, re.IGNORECASE
        )
        if m_infobox:
            src = m_infobox.group(1)
            if src.startswith("//"):
                return "https:" + src
            if src.startswith("/"):
                return "https://tibia.fandom.com" + src
            return src

        # 2) Intento: enlace a File: cuyo nombre contenga el nombre del monstruo
        #    Ej: <a href="/wiki/File:Hellspawn.gif" ...>
        #    Evita coger Flame_Effect.gif, etc.
        variants = _monster_key_variants(monster_name)
        files = re.findall(r'href="/wiki/File:([^"]+?\.gif)"', html, re.IGNORECASE)
        if files:
            # Preferir exact/near match con el nombre del monstruo
            for fname in files:
                for key in variants:
                    # Normalizamos comparando sin espacios/underscores y case-insensitive
                    if re.search(re.escape(key).replace(r"\ ", r"[ _-]?"), fname, re.IGNORECASE):
                        # Construye la URL de redirect directo al archivo del gif
                        return f"https://tibia.fandom.com/wiki/Special:Redirect/file/{quote(fname)}"

        # 3) Fallback último: el primer .gif encontrado (puede ser un efecto)
        m_any = re.search(r'<img[^>]+src="([^"]+?\.gif[^"]*)"', html, re.IGNORECASE)
        if m_any:
            src = m_any.group(1)
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
    Devuelve (data_uri, src_url) del icono del monstruo.
    """
    src_url = get_monster_icon_url(monster_name)
    if not src_url:
        return None, None
    data_uri = get_monster_icon_data_uri(monster_name)
    return data_uri, src_url
