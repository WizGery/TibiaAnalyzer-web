# app_pages/0_Login.py
from __future__ import annotations
import re
import streamlit as st

from ta_core.services.auth_service import signup, login, logout, current_user_id
from ta_core.auth_repo import get_profile, is_username_available, is_email_available
from utils.ui_layout import two_cols, form_cols, inject_base_css

# NO usar st.set_page_config aquí (solo en streamlit_app.py)
st.title("Account")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,10}$")


def _login_tab() -> None:
    col_form, _ = form_cols("sm")
    with col_form:
        with st.form("login_form", clear_on_submit=False):
            # Igual que en Debug: email normalizado, password SIN strip()
            email = st.text_input("Email", key="login_email").strip().lower()
            password = st.text_input("Password", type="password", key="login_pwd")
            submitted = st.form_submit_button("Login")

        if submitted:
            ok, msg = login(email, password)
            text = msg if isinstance(msg, str) else str(msg)
            if ok:
                st.success("Signed in successfully.")
                # Redirige automáticamente al perfil
                st.session_state["_just_logged_in"] = True
                st.rerun()
            else:
                st.error(text)


def _signup_tab() -> None:
    inject_base_css()
    st.caption("**Username** will be publicly visible.")

    st.session_state.setdefault("chk_email", None)
    st.session_state.setdefault("chk_user", None)
    st.session_state.setdefault("user_format_error", False)

    # Email
    col_e_input, col_e_action = two_cols("md")
    with col_e_input:
        su_email = st.text_input("Email", value="", placeholder="you@example.com", key="su_email")
    with col_e_action:
        if st.button("Check email", key="btn_check_email"):
            st.session_state.chk_email = is_email_available(su_email)

    ce = st.session_state.chk_email
    if ce is True:
        st.success("Email available")
    elif ce is False:
        st.error("Email already used")

    # Username
    col_u_input, col_u_action = two_cols("md")
    with col_u_input:
        su_username = st.text_input("Username", value="", placeholder="your_nick", key="su_username")
        username_msg_slot = st.empty()
    with col_u_action:
        if st.button("Check username", key="btn_check_username"):
            if not USERNAME_RE.match(su_username or ""):
                st.session_state.user_format_error = True
                st.session_state.chk_user = None
            else:
                st.session_state.user_format_error = False
                st.session_state.chk_user = is_username_available(su_username)

    if st.session_state.user_format_error:
        with username_msg_slot:
            st.warning("Username must be 3–10 chars, letters/numbers/underscore only.")
    else:
        username_msg_slot.empty()

    cu = st.session_state.chk_user
    if not st.session_state.user_format_error:
        if cu is True:
            st.success("Username available")
        elif cu is False:
            st.error("Username taken")

    # Passwords (como en Debug: no hacemos strip())
    su_pass1 = st.text_input("Password", type="password", key="su_pass1")
    su_pass2 = st.text_input("Confirm password", type="password", key="su_pass2")

    # Submit
    if st.button("Create account", key="btn_signup"):
        if not su_email or not su_username or not su_pass1 or not su_pass2:
            st.error("Please fill all fields.")
            return
        if su_pass1 != su_pass2:
            st.error("Passwords do not match.")
            return
        if not USERNAME_RE.match(su_username or ""):
            st.error("Invalid username format.")
            return

        # ⚠️ Orden CORRECTO como en 8_Debug.py: (email, password, username)
        ok, msg = signup(su_email.strip().lower(), su_pass1, su_username.strip())
        text = msg if isinstance(msg, str) else str(msg)
        if ok:
            st.success("Account created. Please check your email if confirmation is required.")
        else:
            st.error(text)


def _profile_tab() -> None:
    """Vista 'Profile' (antes 'Perfil') solo para usuarios autenticados."""
    uid = current_user_id()
    if not uid:
        st.info("Please sign in to view your profile.")
        return

    prof = get_profile(uid) or {}
    st.subheader("Profile")
    st.write(f"**Username:** {prof.get('username','—')}")
    st.write(f"**Email:** {prof.get('email','—')}")
    st.write(f"**Role:** {prof.get('role','user')}")

    if st.button("Logout"):
        logout()
        st.rerun()


# ----------------------------
# Render según estado de sesión
# ----------------------------
uid = current_user_id()
if st.session_state.pop("_just_logged_in", False) and uid:
    # tras el rerun, ya entra por el camino "logeado"
    pass

if uid:
    (tab_profile,) = st.tabs(["Profile"])
    with tab_profile:
        _profile_tab()
else:
    # Selector controlado en session_state para que no “salte” a Login tras el rerun
    DEFAULT = "Login"
    options = ["Login", "Sign up"]
    current = st.session_state.get("account_mode", DEFAULT)
    try:
        start_index = options.index(current)
    except ValueError:
        start_index = 0

    choice = st.radio(
        label="Account mode",
        options=options,
        index=start_index,
        horizontal=True,
        label_visibility="collapsed",
        key="account_mode",
    )

    if choice == "Login":
        _login_tab()
    else:
        _signup_tab()

