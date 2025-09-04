# app_pages/3_Upload_JSON.py
from __future__ import annotations
from typing import Dict, Any, Tuple, List

import streamlit as st

from utils.data import process_uploads  # uses ta_core.add_uploaded_files under the hood
from ta_core.services.auth_service import current_user_id
from ta_core.repository import load_store, save_store


# --- Guard: solo usuarios logueados ---
uid = current_user_id()
if not uid:
    st.error("No data available")
    st.stop()


# ---- helpers para clave estable de hunts (idéntico al usado en Pending) ----
def _row_key_from_store_item(orig: Dict[str, Any]) -> Tuple[str, str, int]:
    s_start = str(orig.get("Session start", orig.get("session_start", "")))
    s_end = str(orig.get("Session end", orig.get("session_end", "")))
    xp_raw = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
    try:
        xp = int(float(xp_raw))
    except Exception:
        xp = 0
    return (s_start, s_end, xp)


# --- UI minimal ---
st.markdown(
    """
<style>
.main .block-container{padding-top:1.2rem;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Upload JSON")
st.caption("Drop your exported JSON session logs here.")

up = st.file_uploader("Upload files", type=["json"], accept_multiple_files=True)

if up:
    # Snapshot de claves existentes ANTES de importar
    before_store: List[Dict[str, Any]] = load_store()
    before_keys = {_row_key_from_store_item(it) for it in before_store}

    # Procesar subida (añade al store por debajo)
    ok, fail, logs = process_uploads(up)

    # Snapshot DESPUÉS de importar
    after_store: List[Dict[str, Any]] = load_store()
    changed = False

    # A cualquier hunt NUEVO añadido en esta subida le ponemos owner_id = uid si no lo trae
    for it in after_store:
        k = _row_key_from_store_item(it)
        if k not in before_keys:
            # Es nuevo. Si no tiene dueño, se lo asignamos al uploader actual
            if not any(str(it.get(k2, "")).strip() for k2 in ("owner_id", "user_id", "uid", "uploaded_by", "created_by", "author_id")):
                it["owner_id"] = uid
                changed = True

    if changed:
        save_store(after_store)

    # Mensajería
    if ok:
        st.success(f"Added {ok} new file(s).")
    if fail:
        st.error(f"Encountered {fail} error(s) while processing.")

    # Show any detailed log lines (duplicates, etc.)
    if logs:
        for line in logs:
            st.write(f"• {line}")

    st.info("Go to **Zone Averages** or **Pending** to see the updated data.")
