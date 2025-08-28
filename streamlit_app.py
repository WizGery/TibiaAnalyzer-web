import streamlit as st

st.set_page_config(page_title="Tibia Analyzer", page_icon="🧪", layout="wide")

nav = st.navigation([
    st.Page("app_pages/home.py",              title="Home",          icon="🏠", default=True),
    st.Page("app_pages/1_Zone_Averages.py",   title="Zone Averages", icon="📊"),
    st.Page("app_pages/2_Pending.py",         title="Pending",       icon="📝"),
    st.Page("app_pages/3_Upload_JSON.py",     title="Upload JSON",   icon="📤"),
    st.Page("app_pages/4_Statistics.py",      title="Statistics",    icon="📈"),
])
nav.run()
