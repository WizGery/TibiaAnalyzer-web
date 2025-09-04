from __future__ import annotations
from typing import Optional, Literal, Dict
from supabase import Client
from ta_core.services.auth_service import get_supabase

Role = Literal["admin", "user"]


def get_role(user_id: Optional[str]) -> Optional[Role]:
    if not user_id:
        return None
    sb: Client = get_supabase()
    res = (
        sb.table("profiles")
        .select("role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    data = getattr(res, "data", None)
    if not data:
        return None
    return data.get("role")


def get_profile(user_id: Optional[str]) -> Optional[Dict]:
    if not user_id:
        return None
    sb: Client = get_supabase()
    res = (
        sb.table("profiles")
        .select("email,username,role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return getattr(res, "data", None) or None


# --- Disponibilidad usando RPCs seguras ---

def _email_exists(email: str) -> bool:
    if not email:
        return False
    sb: Client = get_supabase()
    res = sb.rpc("email_exists", {"p_email": email}).execute()
    return bool(getattr(res, "data", False))

def _username_exists(username: str) -> bool:
    if not username:
        return False
    sb: Client = get_supabase()
    res = sb.rpc("username_exists", {"p_username": username}).execute()
    return bool(getattr(res, "data", False))

def is_email_available(email: str) -> bool:
    """True si NO existe en auth.users (case-insensitive)."""
    return not _email_exists(email)

def is_username_available(username: str) -> bool:
    """True si NO existe en public.profiles (case-insensitive)."""
    return not _username_exists(username)
