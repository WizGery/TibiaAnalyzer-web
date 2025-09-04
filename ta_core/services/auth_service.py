# ta_core/services/auth_service.py

from gotrue.errors import AuthApiError, AuthRetryableError
from supabase import create_client, Client
import streamlit as st
import os

@st.cache_resource
def _supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase credentials not configured.")
    return create_client(url, key)

def get_supabase() -> Client:
    return _supabase_client()

def _to_text(msg: object) -> str:
    return getattr(msg, "message", None) or str(msg)

def signup(email: str, password: str, username: str) -> tuple[bool, str]:
    """
    Crea usuario con la forma 100% compatible con supabase-py v2:
    sb.auth.sign_up({ "email": ..., "password": ..., "options": {"data": {...}} })
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
                    # user_metadata que recogerá tu trigger para perfilar al usuario
                    "data": {"username": username}
                },
            }
        )
        return True, "Check your inbox to confirm your email."
    except (AuthApiError, AuthRetryableError) as e:
        return False, _to_text(e)
    except Exception as e:
        return False, str(e)

def login(email: str, password: str) -> tuple[bool, str]:
    sb = get_supabase()
    email = (email or "").strip().lower()
    password = (password or "").strip()
    try:
        sb.auth.sign_in_with_password({"email": email, "password": password})
        return True, "Signed in successfully."
    except (AuthApiError, AuthRetryableError) as e:
        return False, _to_text(e)
    except Exception as e:
        return False, str(e)




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
