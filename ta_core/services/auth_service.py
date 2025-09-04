# ta_core/services/auth_service.py
from __future__ import annotations

import os
from typing import Tuple, Optional

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError, AuthRetryableError  # lib oficial


# ----------------------------
# Internals
# ----------------------------

def _get_env(key: str) -> str:
    """Read from st.secrets first, then environment variables."""
    if key in st.secrets:
        v = st.secrets[key]
        if isinstance(v, str) and v.strip():
            return v
    v = os.getenv(key, "")
    if not v:
        raise RuntimeError(f"Missing environment variable: {key}")
    return v


@st.cache_resource(show_spinner=False)
def _get_supabase() -> Client:
    """Internal cached client."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

# Backwards-compat for auth_repo
def get_supabase() -> Client:
    return _get_supabase()


def _to_text(msg: object) -> str:
    """Normalize any object (exceptions, responses) to a human string."""
    if isinstance(msg, str):
        return msg
    # common shapes
    if isinstance(msg, dict):
        for k in ("message", "error_description", "error", "msg", "detail", "hint"):
            if k in msg:
                return str(msg[k])
        return str(msg)
    # gotrue exceptions often expose .message
    m = getattr(msg, "message", None)
    if isinstance(m, str):
        return m
    return str(msg)


# ----------------------------
# Public API
# ----------------------------

def signup(email: str, password: str, username: str) -> tuple[bool, str]:
    email = (email or "").strip().lower()
    username = (username or "").strip()
    sb = get_supabase()
    payload_new = {
        "email": email,
        "password": password,
        "options": {"data": {"username": username}},
    }
    payload_old = {
        "email": email,
        "password": password,
        "data": {"username": username},
    }
    try:
        try:
            sb.auth.sign_up(payload_new)
        except TypeError:
            sb.auth.sign_up(payload_old)
        return True, "Check your inbox to confirm your email."
    except (AuthApiError, AuthRetryableError) as e:
        return False, getattr(e, "message", None) or str(e)


def login(email: str, password: str) -> tuple[bool, str]:
    email = (email or "").strip().lower()
    sb = get_supabase()
    try:
        sb.auth.sign_in_with_password({"email": email, "password": password})
        return True, _to_text("Signed in successfully.")
    except AuthApiError as e:
        # Mensajes comunes de GoTrue:
        # - "Invalid login credentials"
        # - "Email not confirmed"
        # - "User not found"
        msg = getattr(e, "message", None) or str(e)
        # Ayuda contextual
        if "Invalid login credentials" in msg:
            return False, "Invalid login credentials. Tip: check for leading/trailing spaces or reset your password."
        if "Email not confirmed" in msg:
            return False, "Email not confirmed. Please confirm your email before signing in."
        return False, msg
    except AuthRetryableError as e:
        return False, str(e)
    except Exception as e:
        # Por si algo ajeno a Auth (red, httpx, etc.)
        return False, f"Unexpected error: {e}"



def logout() -> Tuple[bool, str]:
    """Sign out current session. Returns (ok, message)."""
    sb = _get_supabase()
    try:
        sb.auth.sign_out()
        return True, _to_text("Signed out.")
    except AuthRetryableError as e:
        return False, _to_text(e)
    except AuthApiError as e:
        return False, _to_text(e)


def current_user_id() -> Optional[str]:
    """Return current user id (or None if no active session)."""
    sb = _get_supabase()
    try:
        u = sb.auth.get_user()
        user = getattr(u, "user", None)
        return getattr(user, "id", None)
    except Exception:
        # If there is no session or token, the SDK may throw; we just return None.
        return None
