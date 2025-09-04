# ta_core/services/auth_service.py
from __future__ import annotations

import os
from typing import Optional, Tuple

import streamlit as st
from supabase import create_client, Client
from gotrue.errors import AuthApiError, AuthRetryableError


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
    """
    Crea un usuario con el payload soportado por supabase-py v2:
      sb.auth.sign_up({
        "email": ...,
        "password": ...,
        "options": {"data": {...}}
      })
    El trigger en la DB leerá user_metadata.data.username para poblar public.profiles.
    """
    sb = get_supabase()

    email = (email or "").strip().lower()
    username = (username or "").strip()
    password = (password or "").strip()

    if not email or not password or not username:
        return False, "Email, password and username are required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    try:
        sb.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {
                    "data": {"username": username}
                },
            }
        )
        return True, "Check your inbox to confirm your email."
    except (AuthApiError, AuthRetryableError) as e:
        return False, _to_text(e)
    except Exception as e:
        return False, str(e)


def login(email: str, password: str) -> Tuple[bool, str]:
    """
    Login por contraseña (GoTrue v2).
    """
    sb = get_supabase()
    email = (email or "").strip().lower()
    password = (password or "").strip()

    try:
        sb.auth.sign_in_with_password({"email": email, "password": password})
        return True, "Signed in successfully."
    except AuthApiError as e:
        # Mensajes habituales: "Invalid login credentials", "Email not confirmed"
        msg = _to_text(e)
        if "Invalid login credentials" in msg:
            return False, "Invalid login credentials."
        if "Email not confirmed" in msg:
            return False, "Email not confirmed. Please confirm your email."
        return False, msg
    except AuthRetryableError as e:
        return False, _to_text(e)
    except Exception as e:
        return False, str(e)


def logout() -> Tuple[bool, str]:
    """Cierra la sesión actual."""
    sb = get_supabase()
    try:
        sb.auth.sign_out()
        return True, "Signed out."
    except (AuthApiError, AuthRetryableError) as e:
        return False, _to_text(e)
    except Exception as e:
        return False, str(e)


def current_user_id() -> Optional[str]:
    """Devuelve el id del usuario actual o None si no hay sesión."""
    sb = get_supabase()
    try:
        u = sb.auth.get_user()
        user = getattr(u, "user", None)
        return getattr(user, "id", None)
    except Exception:
        return None
