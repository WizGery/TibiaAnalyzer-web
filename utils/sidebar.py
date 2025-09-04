# utils/sidebar.py
from __future__ import annotations
from typing import Dict, Tuple, List
import pandas as pd
import streamlit as st
import json

from ta_core.repository import (
    ensure_data_dirs, load_store, save_store,
    export_backup_bytes, clear_hashes,
)
# Importar la lógica de importación de backups desde el servicio (sin ciclos)
from ta_core.services.backup import import_backup_replace_processed
from ta_core.normalizer import normalize_records


def _row_key_from_store_item(orig: Dict) -> Tuple[str, str, int]:
    o_start = str(orig.get("Session start", orig.get("session_start", "")))
    o_end   = str(orig.get("Session end",   orig.get("session_end", "")))
    xo_raw  = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
    try:
        xo = int(xo_raw)
    except Exception:
        xo = 0
    return (o_start, o_end, xo)


def render_global_sidebar():
    """Global sidebar with Backup and Danger zone (no extra separator between them)."""
    ensure_data_dirs()

    # Compacta el espacio justo bajo la línea nativa del menú
    st.markdown("""
    <style>
      /* Reduce el hueco tras la línea nativa del sidebar */
      section[data-testid="stSidebar"] hr { margin-bottom: 6px; }
      /* Evita un gran salto antes del primer expander */
      section[data-testid="stSidebar"] div[data-testid="stExpander"] { margin-top: 6px; }
    </style>
    """, unsafe_allow_html=True)

    # ===== Backup (expander) =====
    with st.expander("💾 Backup", expanded=False):
        # Export
        data_bytes, fname = export_backup_bytes()
        st.download_button(
            "📤 Export backup",
            data=data_bytes,
            file_name=fname,
            mime="application/json",
            use_container_width=True,
            key="sb_export_backup",
        )

        # Import (FULL REPLACE)
        st.caption("Import will REPLACE all current data.")
        bk = st.file_uploader(
            "📥 Import backup (.json)",
            type=["json"],
            accept_multiple_files=False,
            key="sb_import_backup",
            help="Imports the backup and replaces ALL current data. Use with caution.",
        )
        if bk is not None and st.button("Import backup", key="sb_btn_import"):
            do_rerun = False
            try:
                save_store([])  # vacía store
                clear_hashes()  # limpia hashes
                import_backup_replace_processed(bk.read())  # hace el trabajo
                st.success("Backup imported. All previous data was replaced.")
                do_rerun = True
            except (ValueError, OSError, json.JSONDecodeError) as e:
                # Errores esperables del import/IO/JSON. NO capturamos todo Exception.
                st.error(f"Import failed: {e}")
            # <-- fuera del try/except: no se captura la excepción de rerun
            if do_rerun:
                st.rerun()

    # (sin st.markdown('---') aquí; así no aparece una segunda línea)

    # ===== Danger zone (expander) =====
    with st.expander("⚠️ Danger zone", expanded=False):
        st.caption("Destructive actions. Proceed with caution.")

        # Cargar datos para calcular conjuntos processed/pending
        store: List[Dict] = load_store()
        norm_df, pending_df = normalize_records(store)

        processed_keyset = set()
        if isinstance(norm_df, pd.DataFrame) and not norm_df.empty:
            for _, r in norm_df.iterrows():
                processed_keyset.add(
                    (str(r.get("session_start", "")), str(r.get("session_end", "")), int(r.get("xp_gain", 0)))
                )

        pending_keyset = set()
        if isinstance(pending_df, pd.DataFrame) and not pending_df.empty:
            for _, r in pending_df.iterrows():
                pending_keyset.add(
                    (str(r.get("session_start", "")), str(r.get("session_end", "")), int(r.get("xp_gain", 0)))
                )

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
            except Exception as e:
                st.error(f"Could not clear hashes: {e}")
