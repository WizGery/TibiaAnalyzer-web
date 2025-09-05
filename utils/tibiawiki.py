# utils/tibiawiki.py
from __future__ import annotations
import re, base64
from urllib.parse import quote
from typing import Optional, Tuple
import requests
import streamlit as st

WIKI_BASE = "https://tibia.fandom.com/wiki/"

def _normalize_wiki_title(name: str) -> str:
    s = re.sub(r"\s+", " ", str(name or "").strip())

    def cap_hyphenated(token: str) -> str:
        parts = token.split("-")
        parts = [p[:1].upper() + p[1:].lower() if p else "" for p in parts]
        return "-".join(parts)

    words = [cap_hyphenated(w) for w in s.split(" ")]
    return "_".join(words)

def get_monster_icon_url(monster_name: str) -> Optional[str]:
    """Conserva esta si ya la usas en otros sitios."""
    if not monster_name:
        return None
    title = _normalize_wiki_title(monster_name)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TibiaAnalyzer/1.0; +streamlit)"}

    # 1) Special:FilePath (gif/png)
    for ext in (".gif", ".png"):
        try:
            file_url = f"{WIKI_BASE}Special:FilePath/{quote(title + ext, safe=':/_')}"
            r = requests.get(file_url, headers=headers, timeout=10, allow_redirects=True)
            if r.status_code == 200 and r.url and r.url.startswith("http"):
                return r.url
        except Exception:
            pass

    # 2) Fallback: og:image / thumbnail
    try:
        page_url = f"{WIKI_BASE}{quote(title, safe=':/_')}"
        r = requests.get(page_url, headers=headers, timeout=10, allow_redirects=True)
        if r.status_code != 200 or not r.text:
            return None
        html = r.text
        m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if m:
            og = m.group(1)
            return ("https:" + og) if og.startswith("//") else og
        m2 = re.search(r'<img[^>]+class=["\'][^"\']*pi-image-thumbnail[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
                       html, re.IGNORECASE)
        if m2:
            src = m2.group(1)
            return ("https:" + src) if src.startswith("//") else src
    except Exception:
        return None
    return None

@st.cache_data(ttl=60*60*24, show_spinner=False)
def get_monster_icon_bytes(monster_name: str) -> Optional[Tuple[bytes, str, str]]:
    """
    Descarga la imagen del monstruo.
    Devuelve (bytes, mime, final_url) o None si falla.
    """
    url = get_monster_icon_url(monster_name)
    if not url:
        return None
    # Enviar Referer hacia la wiki mejora compatibilidad con el CDN
    title = _normalize_wiki_title(monster_name)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TibiaAnalyzer/1.0; +streamlit)",
        "Referer": f"{WIKI_BASE}{title}",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return None
        mime = r.headers.get("Content-Type", "image/gif")
        return (r.content, mime.split(";")[0], r.url)
    except Exception:
        return None

def get_monster_icon_data_uri(monster_name: str) -> Optional[Tuple[str, str]]:
    """
    Devuelve (data_uri, source_url) para usar en <img src="...">.
    """
    res = get_monster_icon_bytes(monster_name)
    if not res:
        return None
    data, mime, src_url = res
    b64 = base64.b64encode(data).decode("ascii")
    return (f"data:{mime};base64,{b64}", src_url)
