from __future__ import annotations
import streamlit as st

from ta_core.services.auth_service import current_user_id
from ta_core.auth_repo import get_role
from utils.sidebar import render_sidebar

st.set_page_config(page_title="Tibia Analyzer • Home", page_icon="🧭", layout="wide")

def is_logged_in() -> bool:
    return bool(current_user_id())

def is_admin() -> bool:
    uid = current_user_id()
    return bool(uid) and (get_role(uid) or "").lower() == "admin"

pages = [
    st.Page("app_pages/home.py",               title="Home",          icon="🏠"),
    st.Page("app_pages/0_Login.py",            title="Account",       icon="🔐"),
    st.Page("app_pages/1_Zone_Averages.py",    title="Zone Averages", icon="📊"),
    st.Page("app_pages/4_Statistics.py",       title="Statistics",    icon="📈"),
    st.Page("app_pages/_debug_auth.py",       title="debug",    icon="📈"),
]

if is_logged_in():
    pages.extend([
        st.Page("app_pages/2_Pending.py",      title="Pending",     icon="📄"),
        st.Page("app_pages/3_Upload_JSON.py",  title="Upload JSON", icon="🗂️"),
    ])

if is_admin():
    pages.append(st.Page("app_pages/9_Admin.py", title="Admin", icon="🛡️"))

nav = st.navigation(pages)

# <- LLÁMALO ANTES
render_sidebar()

# -> DESPUÉS ejecuta la página seleccionada
nav.run()
