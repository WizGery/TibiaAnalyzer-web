# utils/tibiawiki.py
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

import requests
import streamlit as st

WIKI_BASE = "https://tibia.fandom.com/wiki/"

def _normalize_wiki_title(name: str) -> str:
    """
    Convierte nombres a título de página de TibiaWiki:
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
    # normaliza underscores a espacios
    raw = raw.replace("_", " ")
    raw = re.sub(r"\s+", " ", raw)

    def cap_token(tok: str) -> str:
        # Capitaliza cada parte separada por '-': two-headed -> Two-Headed
        parts = tok.split("-")
        parts = [p[:1].upper() + p[1:].lower() if p else p for p in parts]
        return "-".join(parts)

    tokens = [cap_token(t) for t in raw.split(" ")]
    return "_".join(tokens)

def get_monster_icon_url(monster_name: str) -> Optional[str]:
    """
    Devuelve la URL absoluta del GIF del monstruo en TibiaWiki (si se encuentra).
    """
    title = _normalize_wiki_title(monster_name)
    page_url = f"{WIKI_BASE}{quote(title, safe='-_')}"  # conservar "-" y "_"

    try:
        resp = requests.get(page_url, timeout=10)
        if resp.status_code != 200:
            return None

        # Buscar el primer gif de monstruo en la página (usualmente en infobox)
        match = re.search(r'<img[^>]+src="([^"]+?\.gif)"', resp.text, re.IGNORECASE)
        if match:
            return match.group(1)
    except requests.RequestException as e:
        st.error(f"Failed to fetch monster icon for {monster_name}: {e}")
        return None

    return None
