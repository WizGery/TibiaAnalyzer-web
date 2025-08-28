# utils/guards.py
import streamlit as st

# Toggle centralizado: si algún día quieres volver a exigir login, ponlo a True
# También puedes sobreescribirlo desde .streamlit/secrets.toml con:
# [auth]
# enforce_login = true
_AUTH_ENFORCEMENT_DEFAULT = False
AUTH_ENFORCEMENT = bool(st.secrets.get("auth", {}).get("enforce_login", _AUTH_ENFORCEMENT_DEFAULT))

def require_login(enforce: bool | None = None):
    """
    Si enforce=True y no hay sesión, bloquea. Si es False (por defecto ahora), no bloquea.
    Puedes llamar require_login(True) en una página concreta para forzarla sin tocar el global.
    """
    effective = AUTH_ENFORCEMENT if enforce is None else bool(enforce)
    if effective and not st.session_state.get("auth_ok"):
        st.info("This section requires you to sign in.")
        st.stop()
    # Modo desbloqueado: mostramos una nota suave si no hay sesión
    if not st.session_state.get("auth_ok"):
        st.caption("🔓 Login is optional for now; app_pages are temporarily unlocked.")

def public_note():
    st.caption("Login is optional for now; all sections are temporarily unlocked.")
