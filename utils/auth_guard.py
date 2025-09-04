from __future__ import annotations
from typing import Callable
import streamlit as st
from ta_core.services.auth_service import current_user_id
from ta_core.auth_repo import get_role   # <— CAMBIO AQUÍ

def require_user(render: Callable[[], None]) -> None:
    uid = current_user_id()
    if not uid:
        st.error("No data available")
        st.stop()
    render()

def require_admin(render: Callable[[], None]) -> None:
    uid = current_user_id()
    if not uid:
        st.error("No data available")
        st.stop()
    if get_role(uid) != "admin":
        st.error("No data available")
        st.stop()
    render()
