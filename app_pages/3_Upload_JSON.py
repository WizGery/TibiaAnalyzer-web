# app_pages/3_Upload_JSON.py
from __future__ import annotations
import streamlit as st

from utils.sidebar import render_global_sidebar
from utils.data import process_uploads  # uses ta_core.add_uploaded_files under the hood

# Global sidebar (Backup + Danger zone)
with st.sidebar:
    render_global_sidebar()

# --- Minimal layout & copy in English ---
st.markdown("""
<style>
.main .block-container {max-width: 1100px; margin: 0 auto;}
section[data-testid="stSidebar"] .block-container {padding-top: 1rem;}
</style>
""", unsafe_allow_html=True)

st.title("Upload JSON")
st.caption("Add new hunts by dropping exported .json files from Tibia Analyzer.")

files = st.file_uploader(
    "Upload JSON hunt files (multiple)",
    type=["json"],
    accept_multiple_files=True,
    key="upload_json_files",
)

if files:
    ok, fail, logs = process_uploads(files)

    if ok:
        st.success(f"Added {ok} new file(s).")
    if fail:
        st.error(f"Encountered {fail} error(s) while processing.")

    # Show any detailed log lines (duplicates, etc.)
    if logs:
        for line in logs:
            st.write(f"• {line}")

    st.info("Go to **Zone Averages** or **Pending** to see the updated data.")
