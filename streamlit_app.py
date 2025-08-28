# Home.py
from __future__ import annotations
import streamlit as st
from utils.sidebar import render_global_sidebar

st.set_page_config(
    page_title="Home • Tibia Analyzer",
    page_icon="🧪",
    layout="wide",
)

# Sidebar global (Backup + Danger zone) también en Home
with st.sidebar:
    render_global_sidebar()

# --- CSS: bloque central estrecho y texto centrado ---
st.markdown("""
<style>
/* Compactar el sidebar */
section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* Contenedor centrado visualmente */
.center-wrap {
  max-width: 900px;
  margin: 0 auto;
  text-align: center;
}

/* Asegurar centrado de títulos y párrafos */
.center-wrap h1, .center-wrap h2, .center-wrap h3,
.center-wrap p, .center-wrap li, .center-wrap strong, .center-wrap em {
  text-align: center !important;
}

/* Listas centradas (viñetas dentro) */
.center-wrap ul { list-style-position: inside; padding-left: 0; margin-left: 0; }

/* Pequeños ajustes estéticos */
.hero-sub { font-size: 18px; opacity: .9; margin-top: .25rem; }
</style>
""", unsafe_allow_html=True)

# --- Columna central para centrar el bloque físicamente en la página ---
left, center, right = st.columns([1, 2, 1])
with center:
    st.markdown("<div class='center-wrap'>", unsafe_allow_html=True)

    st.markdown("<h1>🧪 Tibia Analyzer</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='hero-sub'>Upload your hunts, complete pending metadata, and explore zone averages.</p>",
        unsafe_allow_html=True,
    )

    st.markdown("""
**What is this?**

- **Zone Averages:** summaries per zone with expandable details (last 10 raw hunts).
- **Pending:** fill in missing metadata (vocation, mode, zone, level, balance).
- **Upload JSON:** add new hunts from exported <code>.json</code> files.
- **Sidebar:** global **Backup** (export/import) and a **Danger zone** for destructive actions.

*Login is optional for now; pages are temporarily unlocked.*
""")

    st.markdown("</div>", unsafe_allow_html=True)
