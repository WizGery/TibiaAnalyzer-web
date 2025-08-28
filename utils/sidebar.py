# utils/sidebar.py
from __future__ import annotations
from typing import Dict, Tuple, List
import pandas as pd
import streamlit as st

from ta_core.repository import (
    ensure_data_dirs, load_store, save_store,
    export_backup_bytes, import_backup_replace_processed,
    clear_hashes,
)
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
    """Sidebar global con Backup y Danger zone. Llamar desde cada página."""
    ensure_data_dirs()

    st.markdown("### Backup")

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
    bk = st.file_uploader(
        "📥 Import backup (.json)",
        type=["json"],
        accept_multiple_files=False,
        key="sb_import_backup",
        help="Imports the backup and replaces ALL current data. Use with caution.",
    )
    if bk is not None and st.button("Import backup", key="sb_btn_import"):
        try:
            # 1) Vaciar por completo datos actuales
            save_store([])     # deja el store vacío (sin processed ni pending)
            clear_hashes()     # evita que queden huellas de dedupe antiguas

            # 2) Importar el backup
            #   Esta función carga el contenido del backup al store.
            #   Antes sustituía solo 'processed' pero como hemos vaciado,
            #   el efecto es REEMPLAZO TOTAL.
            import_backup_replace_processed(bk.read())

            st.success("Backup imported. All previous data was replaced.")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

    st.markdown("---")
    with st.expander("⚠️ Danger zone", expanded=False):
        st.caption("Destructive actions. Proceed with caution.")

        # Cargar data para calcular conjuntos processed/pending
        store: List[Dict] = load_store()
        norm_df, pending_df = normalize_records(store)

        processed_keyset = set()
        if isinstance(norm_df, pd.DataFrame) and not norm_df.empty:
            for _, r in norm_df.iterrows():
                processed_keyset.add(
                    (str(r.get("session_start","")), str(r.get("session_end","")), int(r.get("xp_gain",0)))
                )

        pending_keyset = set()
        if isinstance(pending_df, pd.DataFrame) and not pending_df.empty:
            for _, r in pending_df.iterrows():
                pending_keyset.add(
                    (str(r.get("session_start","")), str(r.get("session_end","")), int(r.get("xp_gain",0)))
                )

        # 1) Delete processed (keep pending)
        st.checkbox("I understand", key="sb_conf_proc")
        del_proc_disabled = not st.session_state.get("sb_conf_proc", False)
        if st.button("🧹 Delete processed (keep pending)", use_container_width=True,
                     disabled=del_proc_disabled, key="sb_btn_del_processed"):
            new_store = [it for it in store if _row_key_from_store_item(it) not in processed_keyset]
            save_store(new_store)
            st.success("Processed data deleted. Recomputing…")
            st.rerun()

        # 2) Delete pending (keep processed)
        st.checkbox("I understand", key="sb_conf_pend")
        del_pend_disabled = not st.session_state.get("sb_conf_pend", False)
        if st.button("🗑️ Delete pending (keep processed)", use_container_width=True,
                     disabled=del_pend_disabled, key="sb_btn_del_pending"):
            new_store = [it for it in store if _row_key_from_store_item(it) not in pending_keyset]
            save_store(new_store)
            st.success("Pending data deleted. Recomputing…")
            st.rerun()

        st.divider()

        # 3) Clear hashes
        st.checkbox("I understand", key="sb_conf_hash")
        del_hash_disabled = not st.session_state.get("sb_conf_hash", False)
        if st.button("🧯 Clear hashes", use_container_width=True,
                     disabled=del_hash_disabled, key="sb_btn_del_hashes"):
            try:
                clear_hashes()
                st.success("Hashes cleared.")
            except Exception as e:
                st.error(f"Could not clear hashes: {e}")
