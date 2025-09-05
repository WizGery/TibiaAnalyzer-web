# ta_core/services/auth_service.py
from __future__ import annotations

import os
from typing import Optional, Tuple

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError, AuthRetryableError
from utils.debug_console import dbg, debug_enabled



@st.cache_resource
def _supabase_client() -> Client:
    """
    Instancia única de cliente Supabase usando secrets/env.
    """
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase credentials not configured.")
    return create_client(url, key)


def get_supabase() -> Client:
    """API pública para obtener el cliente cacheado."""
    return _supabase_client()


def _to_text(msg: object) -> str:
    """Normaliza cualquier excepción/objeto a string legible."""
    return getattr(msg, "message", None) or str(msg)


# ----------------------------
# Auth API
# ----------------------------
def signup(email: str, password: str, username: str) -> Tuple[bool, str]:
    sb = get_supabase()
    email = (email or "").strip().lower()
    username = (username or "").strip()
    password = (password or "").strip()

    if not email or not password or not username:
        return False, "Email, password and username are required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    try:
        if debug_enabled(): dbg("auth.signup.request", email=email, username=username, password=password)
        res = sb.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"username": username}},
        })
        if debug_enabled(): dbg("auth.signup.response", raw=str(res))
        return True, "Check your inbox to confirm your email."
    except (AuthApiError, AuthRetryableError) as e:
        if debug_enabled(): dbg("auth.signup.error", error=str(e))
        return False, _to_text(e)
    except Exception as e:
        if debug_enabled(): dbg("auth.signup.exception", error=str(e))
        return False, str(e)


def login(email: str, password: str) -> Tuple[bool, str]:
    sb = get_supabase()
    email = (email or "").strip().lower()
    password = (password or "").strip()
    try:
        if debug_enabled(): dbg("auth.login.request", email=email, password=password)
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        if debug_enabled():
            sess = getattr(res, "session", None)
            user = getattr(res, "user", None)
            dbg("auth.login.response",
                has_session=bool(sess),
                has_user=bool(user),
                access_token_len=len(getattr(sess, "access_token", "") or ""),
                refresh_token_len=len(getattr(sess, "refresh_token", "") or ""))
        return True, "Signed in successfully."
    except AuthApiError as e:
        if debug_enabled(): dbg("auth.login.error", error=str(e))
        msg = _to_text(e)
        if "Invalid login credentials" in msg:
            return False, "Invalid login credentials."
        if "Email not confirmed" in msg:
            return False, "Email not confirmed. Please confirm your email."
        return False, msg
    except AuthRetryableError as e:
        if debug_enabled(): dbg("auth.login.retryable", error=str(e))
        return False, _to_text(e)
    except Exception as e:
        if debug_enabled(): dbg("auth.login.exception", error=str(e))
        return False, str(e)


def logout() -> Tuple[bool, str]:
    sb = get_supabase()
    try:
        if debug_enabled(): dbg("auth.logout.request")
        sb.auth.sign_out()
        if debug_enabled(): dbg("auth.logout.ok")
        return True, "Signed out."
    except (AuthApiError, AuthRetryableError) as e:
        if debug_enabled(): dbg("auth.logout.error", error=str(e))
        return False, _to_text(e)
    except Exception as e:
        if debug_enabled(): dbg("auth.logout.exception", error=str(e))
        return False, str(e)


def current_user_id() -> Optional[str]:
    sb = get_supabase()
    try:
        res = sb.auth.get_user()
        user = getattr(res, "user", None)
        uid = getattr(user, "id", None)
        if debug_enabled(): dbg("auth.me", has_user=bool(user), user_id=uid)
        return uid
    except Exception as e:
        if debug_enabled(): dbg("auth.me.exception", error=str(e))
        return None
