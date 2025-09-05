# app_pages/8_Debug.py
from __future__ import annotations
import streamlit as st
from ta_core.services.auth_service import (
    signup, login, logout, current_user_id, get_supabase
)
from utils.debug_console import get_log_text, clear_log, set_debug_enabled, debug_enabled
from ta_core.auth_repo import get_role

# NO st.set_page_config aquí (ya está en streamlit_app.py)

# ---- solo admins ----
_uid = current_user_id()
_is_admin = bool(_uid) and (get_role(_uid) or "").lower() == "admin"
if not _is_admin:
    st.error("Solo admins pueden ver esta página.")
    st.stop()
# ----------------------

st.title("Debug")

st.caption(
    "Herramientas de depuración. No hace cambios destructivos. "
    "Sirve para trazar signup/login y ver logs locales."
)

# ---------- Interruptor de depuración ----------
colA, colB = st.columns([1, 3])
with colA:
    on = st.toggle("Enable logs", value=debug_enabled(), help="Activa la consola de logs")
    set_debug_enabled(on)
with colB:
    if st.button("Clear logs"):
        clear_log()
        st.toast("Logs cleared.")

st.divider()

# ---------- Estado de sesión ----------
uid = current_user_id()
st.write(f"**Current user id:** `{uid or 'None'}`")

# ---------- Forms de prueba: Signup/Login ----------
with st.expander("Sign up (test)", expanded=True):
    su_email = st.text_input("Email", key="dbg_su_email")
    su_user  = st.text_input("Username", key="dbg_su_user")
    su_pass  = st.text_input("Password", type="password", key="dbg_su_pass")
    if st.button("Create account (sign up)"):
        ok, msg = signup(su_email, su_pass, su_user)
        text = (msg or "").strip()
        (st.success if ok else st.error)(text if text else ("OK" if ok else "Error"))

with st.expander("Login (test)", expanded=True):
    li_email = st.text_input("Email", key="dbg_li_email")
    li_pass  = st.text_input("Password", type="password", key="dbg_li_pass")
    if st.button("Login now"):
        ok, msg = login(li_email, li_pass)
        text = (msg or "").strip()
        (st.success if ok else st.error)(text if text else ("OK" if ok else "Error"))

if st.button("Logout"):
    ok, msg = logout()
    text = (msg or "").strip()
    (st.success if ok else st.error)(text if text else ("OK" if ok else "Error"))

st.divider()

# ---------- Consola de logs ----------
st.subheader("Console")
log_text = get_log_text()
if not log_text.strip():
    st.write("_(no logs yet — activa **Enable logs** y prueba signup/login)_")
else:
    st.code(log_text, language="text")
