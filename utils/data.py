# utils/data.py
from __future__ import annotations
from typing import List, Tuple
import pandas as pd
import streamlit as st

# Integra con tu core real
from ta_core.repository import load_store, add_uploaded_files
from ta_core.normalizer import normalize_records


# ---------- Pending ----------
def load_pending_files() -> pd.DataFrame:
    """
    Devuelve el DataFrame de 'pending' usando tu normalizador real.
    """
    store = load_store()
    _, pending_df = normalize_records(store)
    if isinstance(pending_df, pd.DataFrame):
        return pending_df
    return pd.DataFrame()


# ---------- Uploads ----------
def process_uploads(files) -> Tuple[int, int, List[str]]:
    """
    Sube ficheros usando add_uploaded_files() de ta_core.
    Devuelve: (num_ok, num_fail, logs).
    """
    ok, fail, logs = 0, 0, []
    if not files:
        return 0, 0, ["No files to process."]

    try:
        added, skipped = add_uploaded_files(files)
        ok += int(added)
        if added:
            logs.append(f"Added {added} new file(s).")
        if skipped:
            logs.append(f"Ignored {skipped} duplicate file(s).")
    except Exception as e:
        fail += 1
        logs.append(f"Failed to add files: {e}")

    return ok, fail, logs


# ---------- User settings (en memoria por ahora) ----------
def get_user_settings(username: str) -> dict:
    """
    Preferencias básicas guardadas en session_state (no persistente).
    """
    key = f"user_settings__{username or 'anonymous'}"
    return st.session_state.get(key, {"notif": True, "theme": "Auto"})


def save_user_settings(username: str, settings: dict) -> None:
    key = f"user_settings__{username or 'anonymous'}"
    current = st.session_state.get(key, {"notif": True, "theme": "Auto"})
    current.update(settings or {})
    st.session_state[key] = current
