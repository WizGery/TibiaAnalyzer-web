from typing import List, Dict, Callable
import re
import json

import pandas as pd
import streamlit as st

from ta_core.normalizer import normalize_records
from ta_core.aggregator import aggregate_by_zone
from ta_core.export import df_to_csv_bytes
from ta_core.repository import (
    ensure_data_dirs, load_store, save_store,
    add_uploaded_files, dedupe_info,
    export_backup_bytes, import_backup_replace_processed,
    clear_hashes
)

st.set_page_config(
    page_title="Tibia Analyzer Web",
    page_icon="🧪",
    layout="wide",
)

# ===== CSS global =====
st.markdown("""
<style>
/* Centrar el contenido y fijar ancho legible */
.main .block-container {max-width: 1180px; margin: 0 auto;}
/* Compactar sidebar */
section[data-testid="stSidebar"] .block-container {padding-top: 1rem;}
/* Centrar texto en celdas/headers de tablas st.table */
thead tr th, tbody tr td { text-align: center !important; }
</style>
""", unsafe_allow_html=True)

# =========================
# Constants / helpers
# =========================
VOCATION_OPTIONS = ["Knight", "Paladin", "Druid", "Sorcerer", "Monk"]
MODE_OPTIONS = ["Solo", "Duo", "TH"]
TH_MEMBER_OPTIONS = ["Knight", "Paladin", "Druid", "Sorcerer", "Monk", "none"]

def make_level_buckets() -> List[str]:
    buckets = ["8-25", "26-50", "51-75", "76-100"]
    start = 101
    while start <= 951:
        end = start + 49
        buckets.append(f"{start}-{end}")
        start = end + 1
    buckets.append("951-1000")
    start = 1001
    while start <= 1901:
        end = start + 99
        buckets.append(f"{start}-{end}")
        start = end + 1
    return buckets

LEVEL_BUCKETS = make_level_buckets()

TRANSFER_POS_PAT = re.compile(r"(received|get|from|credit|deposit)", re.I)
TRANSFER_NEG_PAT = re.compile(r"(paid|sent|to|debit|withdraw)", re.I)
NUMBER_PAT = re.compile(r"[-+]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|[-+]?\d+")

def parse_real_balance(text: str) -> int:
    total = 0
    for line in text.splitlines():
        nums = NUMBER_PAT.findall(line)
        if not nums:
            continue
        def to_int(s):
            s = s.replace(".", "").replace(",", "")
            try:
                return int(s)
            except Exception:
                return 0
        amount = to_int(nums[0])
        if TRANSFER_NEG_PAT.search(line) and not TRANSFER_POS_PAT.search(line):
            total -= amount
        else:
            total += amount
    return total

# ---------- formatting helpers ----------
def fmt_int(val):
    """Round to int and format with dot thousands (e.g., 23.459)."""
    if pd.isna(val):
        return ""
    try:
        n = float(val)
        n = round(n)
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(val)

def fmt_hours(val):
    """2 decimals, dot thousands."""
    if pd.isna(val):
        return ""
    try:
        n = float(val)
        return f"{n:,.2f}".replace(",", ".")
    except Exception:
        return str(val)

def title_monster(name: str) -> str:
    return (str(name).strip().title()) if name else ""

def style_center(df: pd.DataFrame, fmt_map: Dict[str, Callable] | None = None, hide_index: bool = True):
    """Return a Styler with centered headers/cells and optional column formats."""
    sty = df.style.set_table_styles([
        {"selector": "th", "props": [("text-align", "center")]},
        {"selector": "td", "props": [("text-align", "center")]},
    ]).set_properties(**{"text-align": "center"})
    if fmt_map:
        sty = sty.format(fmt_map)
    if hide_index:
        try:
            sty = sty.hide(axis="index")
        except Exception:
            try:
                sty = sty.hide_index()
            except Exception:
                pass
    return sty
# ----------------------------------------

# =========================
# Init / data
# =========================
ensure_data_dirs()

# --- SIDEBAR (solo flechita nativa para abrir/cerrar) ---
with st.sidebar:
    st.markdown("## Menu")
    st.write("WIP")
    st.markdown("---")

    st.markdown("### Backup")
    data_bytes, fname = export_backup_bytes()
    st.download_button(
        "📤 Export Backup",
        data=data_bytes,
        file_name=fname,
        mime="application/json",
        use_container_width=True,
    )

    bk = st.file_uploader("📥 Import Backup (.json)", type=["json"], accept_multiple_files=False, key="import_backup")
    if bk is not None and st.button("Import now"):
        try:
            import_backup_replace_processed(bk.read())
            st.success("Backup imported (processed replaced, pending kept). Recomputing…")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

    st.markdown("---")
    with st.expander("⚠️ Danger zone", expanded=False):
        st.caption("Destructive actions. Proceed with caution.")

        # — Group 1: delete processed (stacked, full width) —
        with st.container():
            st.checkbox("I understand", key="conf_proc")
            st.button(
                "🧹 Delete processed (keep pending)",
                key="btn_del_processed",
                use_container_width=True,
                disabled=not st.session_state.get("conf_proc", False),
            )
        if st.session_state.get("btn_del_processed"):
            st.session_state["_delete_processed_flag"] = True
            st.rerun()

        # — Group 2: delete pending (stacked, full width) —
        with st.container():
            st.checkbox("I understand", key="conf_pend")
            st.button(
                "🗑️ Delete pending (keep processed)",
                key="btn_del_pending",
                use_container_width=True,
                disabled=not st.session_state.get("conf_pend", False),
            )
        if st.session_state.get("btn_del_pending"):
            st.session_state["_delete_pending_flag"] = True
            st.rerun()

        st.divider()
        # — Group 3: delete hashes —
        with st.container():
            st.checkbox("I understand", key="conf_hash")
            st.button(
                "🧯 Delete hashes",
                key="btn_del_hashes",
                use_container_width=True,
                disabled=not st.session_state.get("conf_hash", False),
            )
        if st.session_state.get("btn_del_hashes"):
            try:
                clear_hashes()
                st.success("Hashes cleared.")
            except Exception as e:
                st.error(f"Could not clear hashes: {e}")

# --- Título grande y centrado ---
st.markdown(
    """
    <h1 style='text-align:center; font-size:48px;'>
        🧪 Tibia Analyzer — Web (Streamlit)
    </h1>
    """,
    unsafe_allow_html=True
)
st.caption("Upload your hunts to the server, complete pending metadata, and explore zone averages.")

store: List[Dict] = load_store()
raw_records: List[Dict] = store
norm_df, pending_df = normalize_records(raw_records)

# ===== Acciones destructivas (aplicación) =====
def row_key_from_store_item(orig: Dict) -> tuple:
    o_start = str(orig.get("Session start", orig.get("session_start", "")))
    o_end   = str(orig.get("Session end",   orig.get("session_end", "")))
    xo_raw  = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
    try:
        xo = int(xo_raw)
    except Exception:
        xo = 0
    return (o_start, o_end, xo)

processed_keyset = set()
if not norm_df.empty:
    for _, r in norm_df.iterrows():
        processed_keyset.add((str(r.get("session_start","")), str(r.get("session_end","")), int(r.get("xp_gain",0))))

pending_keyset = set()
if not pending_df.empty:
    for _, r in pending_df.iterrows():
        pending_keyset.add((str(r.get("session_start","")), str(r.get("session_end","")), int(r.get("xp_gain",0))))

if st.session_state.get("_delete_processed_flag"):
    new_store = [it for it in store if row_key_from_store_item(it) not in processed_keyset]
    save_store(new_store)
    st.session_state["_delete_processed_flag"] = False
    st.success("Processed data deleted. Recomputing…")
    st.rerun()

if st.session_state.get("_delete_pending_flag"):
    new_store = [it for it in store if row_key_from_store_item(it) not in pending_keyset]
    save_store(new_store)
    st.session_state["_delete_pending_flag"] = False
    st.success("Pending data deleted. Recomputing…")
    st.rerun()

# =========================
# Uploader
# =========================
files = st.file_uploader(
    "Upload JSON hunt files (multiple)",
    type=["json"],
    accept_multiple_files=True,
)

if files:
    added, skipped = add_uploaded_files(files)
    if added:
        st.success(f"Added {added} new file(s) to the server.")
    if skipped:
        st.info(f"Ignored {skipped} file(s) — duplicate hash(es).")
    store = load_store()
    raw_records = store
    norm_df, pending_df = normalize_records(raw_records)

# =========================
# Pending utils
# =========================
def top3_monsters(sr: Dict) -> List[str]:
    if isinstance(sr, str):
        try:
            sr = json.loads(sr)
        except Exception:
            sr = {}
    if not isinstance(sr, dict):
        sr = {}
    km = sr.get("Killed Monsters") or sr.get("killed_monsters") or sr.get("monsters") or []
    top = []
    if isinstance(km, list):
        try:
            km_sorted = sorted(km, key=lambda x: int(str(x.get("Count", 0)).replace(",", "")), reverse=True)
        except Exception:
            km_sorted = km
        for m in km_sorted[:3]:
            name = title_monster(m.get("Name") or m.get("name") or "?")
            try:
                cnt = int(str(m.get("Count", 0)).replace(",", ""))
            except Exception:
                cnt = 0
            top.append(f"{name} ({fmt_int(cnt)})")
    while len(top) < 3:
        top.append("")
    return top[:3]

def pending_minitable(df_row: pd.DataFrame) -> pd.DataFrame:
    r = df_row.copy()
    m1, m2, m3 = [], [], []
    for _, rr in r.iterrows():
        t1, t2, t3 = top3_monsters(rr.get("source_raw", {}))
        m1.append(t1); m2.append(t2); m3.append(t3)
    view = pd.DataFrame({
        "Raw XP Gain": r.get("raw_xp_gain"),
        "XP Gain": r.get("xp_gain"),
        "Balance": r.get("balance"),
        "Monster 1": m1,
        "Monster 2": m2,
        "Monster 3": m3,
    })
    return view

# =========================
# Pending (compact)
# =========================
st.markdown(f"## Pending: {len(pending_df)}")

with st.expander("Show/Hide pending", expanded=False):
    if pending_df.empty:
        st.success("No pending records.")
    else:
        st.info("Open a record to edit it. A small table will appear below it.")
        existing_zones = sorted({z for z in norm_df.get("zona", pd.Series(dtype=str)).unique() if str(z).strip()})
        for idx, row in pending_df.reset_index(drop=True).iterrows():
            with st.expander(f"Edit: {row.get('path','(no name)')} — {row.get('session_start','')} → {row.get('session_end','')}"):
                row_df = pending_minitable(pending_df.iloc[[idx]]).reset_index(drop=True)
                st.table(style_center(row_df, {
                    "Raw XP Gain": fmt_int,
                    "XP Gain": fmt_int,
                    "Balance": fmt_int,
                }))

                st.markdown("---")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    try:
                        voc_idx = VOCATION_OPTIONS.index(row.get("vocation","Knight"))
                    except ValueError:
                        voc_idx = 0
                    new_voc = st.selectbox("Vocation", VOCATION_OPTIONS, index=voc_idx, key=f"voc_{idx}")
                with c2:
                    try:
                        mode_idx = MODE_OPTIONS.index(row.get("mode","Solo"))
                    except ValueError:
                        mode_idx = 0
                    new_mode = st.selectbox("Mode", MODE_OPTIONS, index=mode_idx, key=f"mode_{idx}")
                with c3:
                    zone_opts = ["(type)", *existing_zones]
                    start_zone = row.get("zona") if row.get("zona") in zone_opts else "(type)"
                    zone_choice = st.selectbox("Zone", zone_opts, index=zone_opts.index(start_zone), key=f"zone_sel_{idx}")
                    if zone_choice == "(type)":
                        new_zone = st.text_input("Zone (free text)", value=row.get("zona", ""), key=f"zone_text_{idx}")
                    else:
                        new_zone = zone_choice
                with c4:
                    try:
                        lvl_idx = LEVEL_BUCKETS.index(row.get("level_bucket", LEVEL_BUCKETS[0]))
                    except ValueError:
                        lvl_idx = 0
                    new_level = st.selectbox("Level", LEVEL_BUCKETS, index=lvl_idx, key=f"lvl_{idx}")

                duo_voc = None
                th_members = None
                if new_mode == "Duo":
                    duo_voc = st.selectbox("Duo Vocation", VOCATION_OPTIONS, key=f"duo_voc_{idx}")
                elif new_mode == "TH":
                    st.markdown("#### Party Members")
                    cth1, cth2, cth3, cth4 = st.columns(4)
                    with cth1: m1 = st.selectbox("Member 1", TH_MEMBER_OPTIONS, key=f"th1_{idx}")
                    with cth2: m2 = st.selectbox("Member 2", TH_MEMBER_OPTIONS, key=f"th2_{idx}")
                    with cth3: m3 = st.selectbox("Member 3", TH_MEMBER_OPTIONS, key=f"th3_{idx}")
                    with cth4: m4 = st.selectbox("Member 4", TH_MEMBER_OPTIONS, key=f"th4_{idx}")
                    th_members = [m1, m2, m3, m4]

                if st.button("Compute real balance", key=f"open_rb_{idx}"):
                    st.session_state[f"show_rb_{idx}"] = True
                if st.session_state.get(f"show_rb_{idx}", False):
                    with st.expander("Compute real balance", expanded=True):
                        txt = st.text_area("Paste Party Hunt / Transfers text", height=200, key=f"ta_{idx}")
                        if st.button("Compute & apply", key=f"apply_{idx}"):
                            real = parse_real_balance(txt)
                            st.session_state[f"calc_balance_{idx}"] = real
                            st.session_state[f"transfer_text_{idx}"] = txt
                            st.session_state[f"show_rb_{idx}"] = False
                            st.rerun()
                        if st.button("Close", key=f"close_rb_{idx}"):
                            st.session_state[f"show_rb_{idx}"] = False
                            st.rerun()

                calc_val = st.session_state.get(f"calc_balance_{idx}")
                if calc_val is not None:
                    st.success(f"Real balance: {fmt_int(calc_val)}")

                cbtn1, cbtn2, cbtn3 = st.columns([0.34, 0.33, 0.33])
                with cbtn1:
                    if st.button("💾 Save this row", key=f"save_{idx}"):
                        s_start = str(row.get("session_start", ""))
                        s_end = str(row.get("session_end", ""))
                        xp_orig = int(row.get("xp_gain", 0))
                        for orig in store:
                            o_start = str(orig.get("Session start", orig.get("session_start", "")))
                            o_end = str(orig.get("Session end", orig.get("session_end", "")))
                            xo_raw = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
                            xo = int(xo_raw) if xo_raw.isdigit() else 0
                            if (o_start, o_end, xo) == (s_start, s_end, xp_orig):
                                orig["Vocation"], orig["Mode"], orig["Zona"], orig["Level"] = new_voc, new_mode, new_zone, new_level
                                if duo_voc is not None:
                                    orig["Vocation duo"] = duo_voc
                                if th_members is not None:
                                    orig["Party Members"] = th_members
                                if st.session_state.get(f"calc_balance_{idx}") is not None:
                                    orig["Balance"] = int(st.session_state[f"calc_balance_{idx}"])
                                    orig["Balance Real"] = int(st.session_state[f"calc_balance_{idx}"])
                                    orig["Transfer"] = st.session_state.get(f"transfer_text_{idx}", "")
                                break
                        save_store(store)
                        st.success("Row saved. Recomputing…")
                        st.rerun()
                with cbtn2:
                    if st.button("➕ Add Supplies", key=f"add_sup_{idx}"):
                        st.session_state[f"show_supplies_{idx}"] = True
                    if st.session_state.get(f"show_supplies_{idx}", False):
                        with st.expander("Add Supplies", expanded=True):
                            st.write("WIP")
                            if st.button("Close", key=f"close_sup_{idx}"):
                                st.session_state[f"show_supplies_{idx}"] = False
                                st.rerun()
                with cbtn3:
                    if st.button("🗑️ Delete hunt", key=f"del_{idx}"):
                        s_start = str(row.get("session_start", ""))
                        s_end = str(row.get("session_end", ""))
                        xp_orig = int(row.get("xp_gain", 0))
                        new_store = [it for it in store if row_key_from_store_item(it) != (s_start, s_end, xp_orig)]
                        save_store(new_store)
                        st.success("Hunt deleted. Recomputing…")
                        st.rerun()

# =========================
# Filters (compact)
# =========================
st.markdown("---")
st.subheader("Filters")

vocation_options = sorted({v for v in norm_df.get("vocation", pd.Series(dtype=str)).unique() if str(v).strip()})
cfa, cfb, cfc, csp = st.columns([0.22, 0.22, 0.22, 0.34])
with cfa:
    voc_value = st.selectbox("Vocation", vocation_options or [""], index=0, disabled=not bool(vocation_options))
with cfb:
    subset_modes = norm_df[norm_df["vocation"] == voc_value] if voc_value else pd.DataFrame()
    mode_options = sorted({m for m in subset_modes.get("mode", pd.Series(dtype=str)).unique() if str(m).strip()})
    mode_value = st.selectbox("Mode", mode_options or [""], index=0, disabled=not bool(mode_options))
with cfc:
    subset_levels = subset_modes[subset_modes["mode"] == mode_value] if mode_value else subset_modes
    level_options = sorted({b for b in subset_levels.get("level_bucket", pd.Series(dtype=str)).unique() if str(b).strip()})
    level_value = st.selectbox("Level", ["All", *level_options], index=0, disabled=not bool(level_options))

# =========================
# Aggregates with filters
# =========================
filtered = norm_df.copy()
if not filtered.empty and voc_value:
    filtered = filtered[filtered["vocation"] == voc_value]
if not filtered.empty and mode_value:
    filtered = filtered[filtered["mode"] == mode_value]
if not filtered.empty and level_value != "All":
    filtered = filtered[filtered["level_bucket"] == level_value]

agg_df = aggregate_by_zone(filtered)

if not agg_df.empty:
    rename_map = {
        "Zona": "Zone",
        "Hunts": "Hunts",
        "Horas": "Hours",
        "XP Gain (media/h)": "XP Gain (average/h)",
        "Raw XP Gain (media/h)": "Raw XP Gain (average/h)",
        "Supplies (media/h)": "Supplies (average/h)",
        "Loot (media/h)": "Loot (average/h)",
        "Balance (media/h)": "Balance (average/h)",
    }
    agg_df = agg_df.rename(columns=rename_map)
    for c in ["Supplies (average/h)", "Loot (average/h)", "XP Gain (average/h)"]:
        if c in agg_df.columns:
            agg_df = agg_df.drop(columns=[c])
    if "Raw XP Gain (average/h)" in agg_df.columns:
        agg_df["Stamina (average/h)"] = agg_df["Raw XP Gain (average/h)"] * 1.5
    order_cols = ["Zone", "Hunts", "Hours", "Balance (average/h)", "Raw XP Gain (average/h)", "Stamina (average/h)"]
    agg_df = agg_df[[c for c in order_cols if c in agg_df.columns]]

st.markdown("---")
st.markdown("## Zone averages")

if agg_df.empty:
    st.table(pd.DataFrame())
    current_df = agg_df
else:
    sort_cols = list(agg_df.columns)
    sc1, sc2, scsp = st.columns([0.28, 0.28, 0.44])
    with sc1:
        sort_by = st.selectbox("Sort by", options=sort_cols, index=0)
    with sc2:
        order = st.radio("Order", ["Ascending", "Descending"], index=0, horizontal=True)
    ascending = (order == "Ascending")

    current_df = agg_df.sort_values(by=sort_by, ascending=ascending, kind="mergesort")

    st.table(style_center(
        current_df,
        {
            "Hunts": fmt_int,
            "Hours": fmt_hours,
            "Balance (average/h)": fmt_int,
            "Raw XP Gain (average/h)": fmt_int,
            "Stamina (average/h)": fmt_int,
        }
    ))

csv_bytes = df_to_csv_bytes(current_df if current_df is not None and not current_df.empty else pd.DataFrame())
st.download_button(
    label="Export CSV",
    data=csv_bytes,
    file_name="tibia_analyzer_aggregated.csv",
    mime="text/csv",
    disabled=current_df is None or current_df.empty,
)

# =========================
# Statistics
# =========================
with st.expander("Statistics"):
    left, mid, right = st.columns([0.2, 0.6, 0.2])
    with mid:
        total_hunts = len(norm_df)
        total_hours = norm_df["duration_sec"].sum() / 3600.0 if (not norm_df.empty and "duration_sec" in norm_df.columns) else 0.0
        total_places = norm_df["zona"].nunique() if (not norm_df.empty and "zona" in norm_df.columns) else 0
        st.write(f"**Total hunts:** {fmt_int(total_hunts)}")
        st.write(f"**Total hours:** {fmt_hours(total_hours)}")
        st.write(f"**Total places:** {fmt_int(total_places)}")

        if not norm_df.empty:
            voc_counts = norm_df["vocation"].value_counts().rename_axis("Vocation").reset_index(name="Count").reset_index(drop=True)
            mode_counts = norm_df["mode"].value_counts().rename_axis("Mode").reset_index(name="Count").reset_index(drop=True)

            st.markdown("**By Vocation**")
            st.table(style_center(voc_counts, {"Count": fmt_int}, hide_index=True))

            st.markdown("**By Mode**")
            st.table(style_center(mode_counts, {"Count": fmt_int}, hide_index=True))
        else:
            st.info("No processed data yet.")

with st.expander("Debug: dedupe & indices"):
    st.json(dedupe_info())
