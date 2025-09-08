# app_pages/0_Account.py
from __future__ import annotations
import re
import streamlit as st

from ta_core.services.characters_service import refresh_owned_characters, remove_owned_character
from ta_core.services.auth_service import signup, login, logout, current_user_id
from ta_core.auth_repo import get_profile, is_username_available, is_email_available
from utils.ui_layout import two_cols, form_cols, inject_base_css, single_col

# Secciones ocultas (UI aislada)
from app_pages.sections.add_character import render as render_add_character
from app_pages.sections.character_information import render as render_character_info
from app_pages.sections.equipment import render as render_equipment
from app_pages.sections.wod import render as render_wod

# NO usar st.set_page_config aquí (solo en streamlit_app.py)
st.title("Account")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,10}$")


def _login_tab() -> None:
    col_form, _ = form_cols("sm")
    with col_form:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", key="login_email").strip().lower()
            password = st.text_input("Password", type="password", key="login_pwd")
            submitted = st.form_submit_button("Login")

        if submitted:
            ok, msg = login(email, password)
            text = msg if isinstance(msg, str) else str(msg)
            if ok:
                st.success("Signed in successfully.")
                st.session_state["_just_logged_in"] = True
                st.session_state["account_view"] = "profile"
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

    # Passwords
    col_p_input, col_p_confirm = two_cols("md")
    with col_p_input:
        su_pass1 = st.text_input("Password", type="password", key="su_pass1")
        su_pass2 = st.text_input("Confirm password", type="password", key="su_pass2")

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

        ok, msg = signup(su_email.strip().lower(), su_pass1, su_username.strip())
        text = msg if isinstance(msg, str) else str(msg)
        if ok:
            st.success("Account created. Please check your email if confirmation is required.")
        else:
            st.error(text)


def _character_card(uid: str, ch) -> None:
    """Tarjeta de personaje con nombre centrado y botón rojo 'Delete char'."""
    card = st.container(border=True)
    with card:
        st.markdown(
            f"""
            <div style="text-align:center; font-weight:700; margin-bottom:6px;">
                {ch.name}
            </div>
            <div style="margin-bottom:10px; text-align:center;">
                Level {ch.level} · {ch.vocation} · {ch.world}
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Delete char", key=f"del_{ch.name}", type="primary", use_container_width=True):
            if remove_owned_character(uid, ch.name):
                st.rerun()

    # Estiliza en rojo solo los botones 'primary' (Delete)
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button[kind="primary"] {
            background:#ef4444; border-color:#ef4444;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _profile_tab() -> None:
    """Vista 'Profile' solo para usuarios autenticados."""
    uid = current_user_id()
    if not uid:
        st.info("Please sign in to view your profile.")
        return

    # Si el botón dejó encolado un refresh en el ciclo anterior, ejecútalo ahora
    if st.session_state.pop("do_account_refresh", False):
        from ta_core.services import characters_service as _chars
        # limpiar caché de API si existe
        if hasattr(_chars, "_fetch_api_cached") and hasattr(_chars._fetch_api_cached, "clear"):
            _chars._fetch_api_cached.clear()
        # refresco normal (tu función no acepta 'force')
        refresh_owned_characters(uid)
        st.success("Characters refreshed!")
        st.rerun()

    prof = get_profile(uid) or {}
    st.subheader("")

    # Tres columnas de 1er nivel: acciones | detalles | characters
    col_actions, col_details, col_chars = st.columns([1, 1, 2], gap="large")

    # --- Acciones ---
    with col_actions:
        def _to(view: str) -> None:
            st.session_state["account_view"] = view

        st.button("Add character", on_click=lambda: _to("add_character"), use_container_width=True)
        st.button("Character information", on_click=lambda: _to("character_info"), use_container_width=True)
        st.button("Equipment", on_click=lambda: _to("equipment"), use_container_width=True)
        st.button("WoD", on_click=lambda: _to("wod"), use_container_width=True)

        # Botón Refresh (mismo estilo que el resto)
        def _queue_refresh() -> None:
            st.session_state["do_account_refresh"] = True  # se procesará al inicio del próximo ciclo

        st.button(
            "Refresh",
            key="btn_account_refresh",     # key única para evitar colisiones
            on_click=_queue_refresh,
            use_container_width=True,
        )

        def _do_logout() -> None:
            logout()
            st.session_state["account_view"] = None
            st.rerun()
        st.button("Logout", on_click=_do_logout, use_container_width=True)

    # --- Detalles de cuenta (marco ajustado al contenido) ---
    with col_details:
        st.markdown(
            f"""
            <div style="
                display:inline-block;
                border:1px solid rgba(255,255,255,0.2);
                border-radius:12px;
                padding:12px 20px;
                margin-top:4px;
            ">
                <p><strong>Username:</strong> {prof.get('username', '—')}</p>
                <p><strong>Email:</strong> <a href="mailto:{prof.get('email', '—')}" target="_blank">{prof.get('email', '—')}</a></p>
                <p><strong>Role:</strong> {prof.get('role', 'user')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- Characters (grid) ---
    with col_chars:
        st.markdown(
            """
            <h3 style="text-align:center; margin-bottom: 1rem;">
                Characters
            </h3>
            """,
            unsafe_allow_html=True,
        )

        chars = refresh_owned_characters(uid)

        if not chars:
            st.info("No data available")
        else:
            PER_ROW = 3
            idx = 0
            while idx < len(chars):
                row_cols = st.columns(PER_ROW, gap="large")
                for c in row_cols:
                    if idx >= len(chars):
                        break
                    ch = chars[idx]
                    idx += 1
                    with c:
                        _character_card(uid, ch)



# ----------------------------
# Render según estado de sesión
# ----------------------------
uid = current_user_id()
if st.session_state.pop("_just_logged_in", False) and uid:
    pass

if uid:
    account_view = st.session_state.get("account_view") or "profile"
    if account_view == "add_character":
        render_add_character(on_back=lambda: st.session_state.update(account_view="profile"))
    elif account_view == "character_info":
        render_character_info(on_back=lambda: st.session_state.update(account_view="profile"))
    elif account_view == "equipment":
        render_equipment(on_back=lambda: st.session_state.update(account_view="profile"))
    elif account_view == "wod":
        render_wod(on_back=lambda: st.session_state.update(account_view="profile"))
    else:
        (tab_profile,) = st.tabs(["Profile"])
        with tab_profile:
            _profile_tab()
else:
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
