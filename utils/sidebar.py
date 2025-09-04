from __future__ import annotations
from typing import Dict, List, Tuple, Any
import json

import pandas as pd
import streamlit as st

# ===== Dominio =====
# Backup: ahora ambas funciones vienen del servicio dedicado
from ta_core.services.backup import (
    export_backup_bytes,
    import_backup_replace_processed,
)

# Persistencia y utilidades de datos
from ta_core.repository import (
    load_store,
    save_store,
    clear_hashes,
)

from ta_core.normalizer import normalize_records
from ta_core.services.auth_service import current_user_id
from ta_core.auth_repo import get_role


# ----------------------------
# Helpers de auth
# ----------------------------
def _is_logged_in() -> bool:
    return bool(current_user_id())


def _is_admin() -> bool:
    uid = current_user_id()
    return bool(uid) and (get_role(uid) or "").lower() == "admin"


# ----------------------------
# Helpers de store/keys
# ----------------------------
def _row_key_from_store_item(orig: Dict[str, Any]) -> Tuple[str, str, int]:
    """
    Clave estable para comparar hunts entre store y dataframes:
    (session_start, session_end, xp_gain:int)
    """
    s_start = str(orig.get("Session start", orig.get("session_start", "")))
    s_end = str(orig.get("Session end", orig.get("session_end", "")))
    xp_raw = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
    try:
        xp = int(float(xp_raw))
    except Exception:
        xp = 0
    return (s_start, s_end, xp)


# ----------------------------
# Expanders
# ----------------------------
def _exp_backup() -> None:
    """
    Expander de Backup con:
      - Export (devuelve (bytes, filename))
      - Import (REPLACE ALL) usando import_backup_replace_processed
    """
    with st.sidebar.expander("💾 Backup", expanded=False):
        # ---------- Export ----------
        try:
            data_bytes, fname = export_backup_bytes()
            mime = "application/json" if str(fname).lower().endswith(".json") else "application/zip"
            st.download_button(
                "📤 Export backup",
                data=data_bytes,
                file_name=fname,
                mime=mime,
                use_container_width=True,
                key="sb_export_backup",
            )
        except (OSError, ValueError) as e:
            st.error(f"Export failed: {e}")

        # ---------- Import ----------
        st.caption("Import will REPLACE all current data.")
        uploader = st.file_uploader(
            "📥 Import backup (.json)",
            type=["json"],
            accept_multiple_files=False,
            key="sb_import_backup",
            help="Imports the backup and replaces ALL current data. Use with caution.",
        )

        if uploader is not None and st.button("Import backup", key="sb_btn_import"):
            do_rerun = False
            try:
                raw_bytes = uploader.read()
                # Reemplaza all y limpia hashes internamente
                import_backup_replace_processed(raw_bytes)
                st.success("Backup imported. All previous data was replaced.")
                do_rerun = True
            except (ValueError, OSError, json.JSONDecodeError) as e:
                st.error(f"Import failed: {e}")

            if do_rerun:
                st.rerun()


def _exp_danger_zone() -> None:
    """
    Expander de Danger zone con:
      1) Delete processed (mantener pending)
      2) Delete pending (mantener processed)
      3) Clear hashes
    """
    with st.sidebar.expander("⚠️ Danger zone", expanded=False):
        st.caption("Destructive actions. Proceed with caution.")

        # Cargar datos para calcular conjuntos processed/pending
        store: List[Dict[str, Any]] = load_store()
        norm_df, pending_df = normalize_records(store)

        processed_keyset = set()
        if isinstance(norm_df, pd.DataFrame) and not norm_df.empty:
            for _, r in norm_df.iterrows():
                try:
                    key = (
                        str(r.get("session_start", "")),
                        str(r.get("session_end", "")),
                        int(r.get("xp_gain", 0)),
                    )
                except Exception:
                    key = (
                        str(r.get("session_start", "")),
                        str(r.get("session_end", "")),
                        0,
                    )
                processed_keyset.add(key)

        pending_keyset = set()
        if isinstance(pending_df, pd.DataFrame) and not pending_df.empty:
            for _, r in pending_df.iterrows():
                try:
                    key = (
                        str(r.get("session_start", "")),
                        str(r.get("session_end", "")),
                        int(r.get("xp_gain", 0)),
                    )
                except Exception:
                    key = (
                        str(r.get("session_start", "")),
                        str(r.get("session_end", "")),
                        0,
                    )
                pending_keyset.add(key)

        # 1) Delete processed (keep pending)
        st.checkbox("I understand", key="sb_conf_proc")
        if st.button(
            "🧹 Delete processed",
            use_container_width=True,
            disabled=not st.session_state.get("sb_conf_proc", False),
            key="sb_btn_del_processed",
        ):
            new_store = [it for it in store if _row_key_from_store_item(it) not in processed_keyset]
            save_store(new_store)
            st.success("Processed data deleted. Recomputing")
            st.rerun()

        # 2) Delete pending (keep processed)
        st.checkbox("I understand", key="sb_conf_pend")
        if st.button(
            "🗑️ Delete pending",
            use_container_width=True,
            disabled=not st.session_state.get("sb_conf_pend", False),
            key="sb_btn_del_pending",
        ):
            new_store = [it for it in store if _row_key_from_store_item(it) not in pending_keyset]
            save_store(new_store)
            st.success("Pending data deleted. Recomputing")
            st.rerun()

        st.divider()

        # 3) Clear hashes
        st.checkbox("I understand", key="sb_conf_hash")
        if st.button(
            "🧯 Clear hashes",
            use_container_width=True,
            disabled=not st.session_state.get("sb_conf_hash", False),
            key="sb_btn_del_hashes",
        ):
            try:
                clear_hashes()
                st.success("Hashes cleared.")
            except (RuntimeError, ValueError, OSError) as e:
                st.error(f"Could not clear hashes: {e}")


# ----------------------------
# Render público
# ----------------------------
def render_sidebar() -> None:
    """
    Dibuja utilidades del sidebar SOLO si el usuario es admin.
    Llama a esta función **antes** de nav.run() en streamlit_app.py.
    """
    if not (_is_logged_in() and _is_admin()):
        return

    # margen suave, sin divider extra para no crear líneas duplicadas
    st.sidebar.write("")
    _exp_backup()
    st.sidebar.write("")
    _exp_danger_zone()
