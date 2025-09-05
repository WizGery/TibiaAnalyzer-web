# app_pages/8_Debug.py
from __future__ import annotations
import streamlit as st
from ta_core.services.auth_service import get_supabase, login, signup, logout, current_user_id
from utils.debug_console import get_log_text, clear_log, set_debug_enabled, debug_enabled

# ❌ NO st.set_page_config aquí
st.title("Debug console")

# Solo admins (si quieres quitar la barrera, comenta este bloque)
try:
    from ta_core.services.auth_service import get_supabase
    from ta_core.auth_repo import get_role
    from ta_core.services.auth_service import current_user_id
    uid = current_user_id()
    role = (get_role(uid) or "").lower() if uid else ""
    if role != "admin":
        st.warning("Solo admins pueden ver esto.")
        st.stop()
except Exception:
    pass

st.title("Debug console")

c0, c1, c2, c3 = st.columns([1,1,1,1])
with c0:
    en = st.toggle("Enable debug hooks", value=debug_enabled(), help="Muestra en vivo las llamadas a auth.*")
    set_debug_enabled(en)
with c1:
    if st.button("Clear log"):
        clear_log()
with c2:
    if st.button("Who am I?"):
        uid = current_user_id()
        st.write({"user_id": uid})
with c3:
    if st.button("Sign out"):
        st.write(logout())

st.divider()

st.subheader("Auth quick tests")

tab1, tab2, tab3 = st.tabs(["Login", "Sign up", "Session"])
with tab1:
    with st.form("dbg_login"):
        em = st.text_input("Email", value="", key="dbg_log_email")
        pw = st.text_input("Password", value="", type="password", key="dbg_log_pw")
        submit = st.form_submit_button("Login (auth.sign_in_with_password)")
    if submit:
        ok, msg = login(em, pw)
        st.write({"ok": ok, "msg": msg})

with tab2:
    with st.form("dbg_signup"):
        em = st.text_input("Email", value="", key="dbg_su_email")
        un = st.text_input("Username", value="", key="dbg_su_user")
        pw = st.text_input("Password", value="", type="password", key="dbg_su_pw")
        submit = st.form_submit_button("Create account (auth.sign_up)")
    if submit:
        ok, msg = signup(em, pw, un)
        st.write({"ok": ok, "msg": msg})

with tab3:
    sb = get_supabase()
    try:
        sess = sb.auth.get_session()
        user = sb.auth.get_user()
    except Exception as e:
        sess = None
        user = None
        st.error(f"session error: {e}")

    st.write({
        "has_session": bool(getattr(sess, 'session', None) or sess),
        "access_token_len": len(getattr(getattr(sess, "session", None) or sess, "access_token", "") or ""),
        "refresh_token_len": len(getattr(getattr(sess, "session", None) or sess, "refresh_token", "") or ""),
    })
    st.write({"raw_user": str(user)})

st.divider()
st.subheader("Live log")
st.code(get_log_text() or "<empty>", language="text")
