# utils/auth.py
import re
import streamlit as st
import streamlit as stauth


def _is_bcrypt_hash(s: str) -> bool:
    return isinstance(s, str) and s.startswith("$2") and len(s) > 20

def _hash_password_if_needed(pw: str) -> str:
    if not pw:
        return pw
    if _is_bcrypt_hash(pw):
        return pw
    return stauth.Hasher.hash(pw)   # ✅ forma correcta en 0.4.x


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _build_usernames_from_secrets() -> dict:
    """
    Estructura esperada en .streamlit/secrets.toml:

    [auth.users.user1]
    name = "Gerard"
    email = "uhgery@gmail.com"
    password = "1234"  # dev (se hashea al vuelo)

    Login permitido con:
      - la clave del usuario (p.ej. "user1")
      - el email ("uhgery@gmail.com")
      - el nombre en slug ("gerard")
    """
    cfg_users = st.secrets.get("auth", {}).get("users", {})
    usermap = {}

    for cfg_key, u in cfg_users.items():
        name = u.get("name", "") or ""
        email = (u.get("email", "") or "").lower()
        pw = _hash_password_if_needed(u.get("password", "") or "")

        base = {
            "name": name,
            "email": email,
            "password": pw,
        }

        # Claves aceptadas para login
        keys = {cfg_key}
        if email:
            keys.add(email)
        sname = _slug(name)
        if sname:
            keys.add(sname)

        for k in keys:
            usermap[k] = base

    return usermap


def get_authenticator() -> stauth.Authenticate:
    return stauth.Authenticate(
        credentials={"usernames": _build_usernames_from_secrets()},
        cookie_name="tibia_analyzer_auth",
        cookie_key="tibia_analyzer_auth_key",
        cookie_expiry_days=30,
        preauthorized={},
    )


def _set_auth_state(ok: bool, name: str | None = None, username: str | None = None):
    st.session_state["auth_ok"] = bool(ok)
    st.session_state["auth_user"] = (
        {"username": username or "", "name": name or ""} if ok else None
    )


def login_sidebar():
    authenticator = get_authenticator()

    fields = {
        "Form name": "Iniciar sesión",
        "Username": "Usuario / Email / Nombre",
        "Password": "Contraseña",
    }

    result = authenticator.login(location="sidebar", fields=fields, key="login")

    # En 0.4.x puede devolver None en el primer render → sin romper
    if isinstance(result, tuple) and len(result) == 3:
        name, auth_status, username = result
    else:
        name = username = None
        auth_status = None

    if auth_status is True:
        _set_auth_state(True, name=name, username=username)
        st.sidebar.success(f"Hola, {name}")
        authenticator.logout(
            button_name="Cerrar sesión",
            location="sidebar",
            key="logout",
        )
    elif auth_status is False:
        _set_auth_state(False)
        st.sidebar.error("Usuario o contraseña incorrectos.")
    else:
        _set_auth_state(False)
        st.sidebar.info("Inicia sesión para acceder a secciones privadas.")

    return auth_status
