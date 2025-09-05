# utils/debug_console.py
from __future__ import annotations
import time, json, os
import streamlit as st

REDACT_KEYS = {"password", "access_token", "refresh_token", "apikey", "api_key", "authorization", "secret", "supabase_anon_key"}

def _redact_value(k: str, v):
    k_low = k.lower()
    if any(k_low == rk or rk in k_low for rk in REDACT_KEYS):
        s = str(v)
        if not s:
            return ""
        # mostramos solo longitud para comparar
        return f"<redacted:{len(s)}>"
    return v

def _redact(obj):
    try:
        if isinstance(obj, dict):
            return {k: _redact_value(k, _redact(v)) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_redact(x) for x in obj]
    except Exception:
        pass
    return obj

def dbg(msg: str, **kv):
    """Añade una línea a la consola de debug (sanitizada)."""
    if "debug_log" not in st.session_state:
        st.session_state["debug_log"] = []
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    if kv:
        safe = _redact(kv)
        try:
            payload = json.dumps(safe, ensure_ascii=False)
        except Exception:
            payload = str(safe)
        line += " " + payload
    st.session_state["debug_log"].append(line)

def get_log_text() -> str:
    return "\n".join(st.session_state.get("debug_log", []))

def clear_log():
    st.session_state["debug_log"] = []

def set_debug_enabled(flag: bool):
    st.session_state["debug_enabled"] = bool(flag)

def debug_enabled() -> bool:
    return bool(st.session_state.get("debug_enabled", True))
