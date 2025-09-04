from __future__ import annotations
import streamlit as st
from utils.auth_guard import require_admin

def _render():
    st.title("Admin")
    st.write("Solo admins pueden ver esto.")

require_admin(_render)
