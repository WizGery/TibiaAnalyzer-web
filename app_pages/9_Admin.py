from __future__ import annotations
import pandas as pd
import streamlit as st

from utils.auth_guard import require_admin
from ta_core.repository import load_store
from ta_core.normalizer import normalize_records
from ta_core.auth_repo import get_profile

# Import específico de la librería postgrest para capturar 204/errores
try:
    from postgrest.exceptions import APIError  # type: ignore
except Exception:  # si la import no existe en tu env, definimos un placeholder
    class APIError(Exception):
        pass


# ---------- Helpers ----------
def _row_key_from_store_item(orig: dict) -> tuple[str, str, int]:
    s_start = str(orig.get("Session start", orig.get("session_start", "")))
    s_end = str(orig.get("Session end", orig.get("session_end", "")))
    xp_raw = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
    try:
        xp = int(xp_raw)
    except ValueError:
        try:
            xp = int(float(xp_raw))
        except ValueError:
            xp = 0
    return (s_start, s_end, xp)


def _row_key_from_norm_row(row: pd.Series) -> tuple[str, str, int]:
    s_start = str(row.get("session_start", ""))
    s_end = str(row.get("session_end", ""))
    try:
        xp = int(row.get("xp_gain", 0))
    except Exception:
        xp = 0
    return (s_start, s_end, xp)


def _owner_map(store_rows: list[dict]) -> dict[tuple[str, str, int], str]:
    m: dict[tuple[str, str, int], str] = {}
    for it in store_rows:
        key = _row_key_from_store_item(it)
        # owner puede venir con distintas claves; si no hay, usamos "unknown"
        owner = (
            it.get("owner_user_id")
            or it.get("owner_id")
            or it.get("user_id")
            or it.get("uid")
            or it.get("uploaded_by")
            or it.get("created_by")
            or it.get("author_id")
            or "unknown"
        )
        m[key] = str(owner)
    return m


@st.cache_data(show_spinner=False)
def _safe_username(user_id: str) -> str:
    """
    Devuelve un nombre amigable a partir del user_id.
    - Evita consultas para 'unknown' o cadenas vacías.
    - Captura APIError (p. ej. 204 No Content) y hace fallback.
    """
    uid = (user_id or "").strip()
    if not uid or uid.lower() == "unknown":
        return "unknown"
    try:
        prof = get_profile(uid) or {}
    except APIError:
        # Supabase devolvió 204 u otro error → fallback
        return uid[:8]
    username = (prof.get("username") or "").strip()
    return username if username else uid[:8]


def _render() -> None:
    st.title("Admin")
    st.write("Solo admins pueden ver esto.")

    store = load_store()
    norm_df, pending_df = normalize_records(store)

    owner_by_key = _owner_map(store)

    def map_owner(df: pd.DataFrame) -> pd.Series:
        return df.apply(lambda r: owner_by_key.get(_row_key_from_norm_row(r), "unknown"), axis=1)

    norm_df = norm_df.copy()
    pending_df = pending_df.copy()
    norm_df["owner"] = map_owner(norm_df)
    pending_df["owner"] = map_owner(pending_df)

    # Conteos: Total (finalizados) y Pending (sin completar)
    total_final = (
        norm_df.groupby("owner").size().rename("Total hunts").reset_index()
        if not norm_df.empty else pd.DataFrame({"owner": [], "Total hunts": []})
    )
    total_pending = (
        pending_df.groupby("owner").size().rename("Pending").reset_index()
        if not pending_df.empty else pd.DataFrame({"owner": [], "Pending": []})
    )

    counts = pd.merge(total_final, total_pending, on="owner", how="outer").fillna(0)
    if counts.empty:
        st.subheader("Hunt Sessions by User")
        st.info("No data available")
        return

    counts["Total hunts"] = counts["Total hunts"].astype(int)
    counts["Pending"] = counts["Pending"].astype(int)

    # Resolver nombres de usuario de forma segura y cacheada
    counts["User"] = counts["owner"].map(_safe_username)

    counts = counts[["User", "owner", "Total hunts", "Pending"]].sort_values(
        ["Total hunts", "Pending", "User"], ascending=[False, False, True]
    )

    st.subheader("Hunt Sessions by User")
    st.dataframe(counts, use_container_width=True)


require_admin(_render)
