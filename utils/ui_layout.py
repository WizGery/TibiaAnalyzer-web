# utils/ui_layout.py
from __future__ import annotations
from typing import Literal, Tuple, Dict

import streamlit as st

# Tamaños disponibles
RowSize = Literal["sm", "md", "lg"]

# Ratios para filas con: [input | botón | estado]
# md es el tamaño "default" (Register)
_ROW_SPECS: Dict[RowSize, Tuple[float, float, float]] = {
    "sm": (0.25, 0.22, 0.22),
    "md": (0.25, 0.25, 0.25),  # DEFAULT
    "lg": (0.72, 0.14, 0.14),
}

def three_cols(size: RowSize = "md"):
    """Crea 3 columnas: [input | botón | estado]."""
    ratios = _ROW_SPECS.get(size, _ROW_SPECS["md"])
    return st.columns(ratios, vertical_alignment="bottom")

def single_col(size: RowSize = "md"):
    """
    Devuelve una única columna del ancho definido en _ROW_SPECS.
    Útil para inputs sueltos (ej. login).
    """
    ratios = _ROW_SPECS.get(size, _ROW_SPECS["md"])
    return st.columns([ratios[0]])  # solo usamos la primera proporción (input)

def two_cols(size: RowSize = "md"):
    """
    Crea 2 columnas: [input | (botón+estado)].
    Útil cuando quieres que el estado vaya pegado al botón.
    """
    r = _ROW_SPECS.get(size, _ROW_SPECS["md"])
    return st.columns([r[0], r[1] + r[2]], vertical_alignment="bottom", gap="small")

def inject_base_css() -> None:
    """Estilos base (pills compactas). Llamar 1 vez por página."""
    st.markdown(
        """
        <style>
          .status-pill{
            display:inline-block; padding:6px 10px; border-radius:8px;
            font-size:0.9rem; font-weight:600;
          }
          .ok  { background:#123c2b; color:#d9f7e9; }
          .bad { background:#3c1212; color:#ffe1e1; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def pill_ok(text: str) -> None:
    st.markdown(f'<span class="status-pill ok">{text}</span>', unsafe_allow_html=True)

def pill_bad(text: str) -> None:
    st.markdown(f'<span class="status-pill bad">{text}</span>', unsafe_allow_html=True)

def inline_button_and_status(
    parent_col,
    *,
    button_label: str,
    status: bool | None,
    ok_text: str,
    bad_text: str,
    key: str,
    split: Tuple[float, float] = (0.40, 0.60),
) -> bool:
    """
    Pinta dentro de `parent_col` dos sub-columnas en línea:
    [ botón | pill de estado ]. Devuelve True si se clicó el botón.
    - status: True → ok_text, False → bad_text, None → nada
    - split: proporción entre botón y estado dentro de la columna
    """
    bcol, scol = parent_col.columns(split, gap="small")
    clicked = bcol.button(button_label, key=key)
    if status is True:
        with scol:
            pill_ok(ok_text)
    elif status is False:
        with scol:
            pill_bad(bad_text)
    return clicked

def form_cols(size: RowSize = "md"):
    """
    Devuelve 2 columnas [form | relleno] donde la izquierda ocupa el mismo
    ancho que el 'input' del layout elegido (sm/md/lg). Útil para encajonar
    st.form sin que se estire a toda la página.
    """
    ratios = _ROW_SPECS.get(size, _ROW_SPECS["md"])
    w = ratios[0]                 # usamos el ancho del input de ese tamaño
    return st.columns([w, 1 - w]) # izquierda = form, derecha = relleno