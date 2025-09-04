# app_pages/home.py
from __future__ import annotations
import streamlit as st

# ——— Estilos para centrar el bloque y su contenido ———
st.markdown("""
<style>
/* compactar un poco el sidebar */
section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* bloque central + texto centrado */
.center-wrap { max-width: 900px; margin: 0 auto; text-align: center; }
.center-wrap h1, .center-wrap h2, .center-wrap h3,
.center-wrap p, .center-wrap li, .center-wrap strong, .center-wrap em {
  text-align: center !important;
}
.center-wrap ul { list-style-position: inside; padding-left: 0; margin-left: 0; }

/* subtítulo */
.hero-sub { font-size: 18px; opacity: .9; margin-top: .35rem; }
</style>
""", unsafe_allow_html=True)

# ——— Centrado físico del bloque en la página ———
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
