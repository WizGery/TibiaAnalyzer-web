# pages/1_Zone_Averages.py
from __future__ import annotations
from typing import List, Dict, Callable
import re
import pandas as pd
import streamlit as st

from ta_core.repository import load_store
from ta_core.normalizer import normalize_records
from ta_core.aggregator import aggregate_by_zone
from ta_core.export import df_to_csv_bytes

from utils.sidebar import render_global_sidebar

with st.sidebar:
    render_global_sidebar()


# ---------- helpers ----------
def fmt_int(val):
    if pd.isna(val):
        return ""
    try:
        n = round(float(val))
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(val)

def fmt_hours(val):
    if pd.isna(val):
        return ""
    try:
        return f"{float(val):,.2f}".replace(",", ".")
    except Exception:
        return str(val)

def style_center(
    df: pd.DataFrame,
    fmt_map: Dict[str, Callable] | None = None,
    hide_index: bool = True,
):
    sty = (
        df.style.set_table_styles(
            [
                {"selector": "th", "props": [("text-align", "center")]},
                {"selector": "td", "props": [("text-align", "center")]},
            ]
        ).set_properties(**{"text-align": "center"})
    )
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

# numeric sort for level ranges like "401-450"
_first_num_re = re.compile(r"\d+")
def _bucket_sort_key(s: str) -> int:
    if not isinstance(s, str):
        return 10**9
    m = _first_num_re.search(s)
    return int(m.group()) if m else 10**9

# duration "Xh Ymin" / "Xmin"
def fmt_duration_text(hours_float: float) -> str:
    try:
        mins = int(round(float(hours_float) * 60))
    except Exception:
        return ""
    h, m = divmod(mins, 60)
    if h <= 0:
        return f"{m}min"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}min"

# ---------- data ----------
st.title("Zone Averages")
store = load_store()
norm_df, pending_df = normalize_records(store)
LEVEL_BUCKETS = make_level_buckets()

# ---------- filters ----------
st.markdown("### Filters")
vocation_options = sorted(
    {v for v in norm_df.get("vocation", pd.Series(dtype=str)).unique() if str(v).strip()}
)
cfa, cfb, cfc, _ = st.columns([0.22, 0.22, 0.22, 0.34])

with cfa:
    default_voc_idx = vocation_options.index("Knight") if "Knight" in vocation_options else 0
    voc_value = st.selectbox(
        "Vocation",
        vocation_options or [""],
        index=default_voc_idx if vocation_options else 0,
        disabled=not bool(vocation_options),
        key="za_voc",
    )

with cfb:
    subset_modes = norm_df[norm_df["vocation"] == voc_value] if voc_value else pd.DataFrame()
    mode_options = sorted(
        {m for m in subset_modes.get("mode", pd.Series(dtype=str)).unique() if str(m).strip()}
    )
    default_mode_idx = mode_options.index("Solo") if "Solo" in mode_options else 0
    mode_value = st.selectbox(
        "Mode",
        mode_options or [""],
        index=default_mode_idx if mode_options else 0,
        disabled=not bool(mode_options),
        key="za_mode",
    )

with cfc:
    subset_levels = subset_modes[subset_modes["mode"] == mode_value] if mode_value else subset_modes
    level_raw = {
        b for b in subset_levels.get("level_bucket", pd.Series(dtype=str)).unique() if str(b).strip()
    }
    level_options = sorted(level_raw, key=_bucket_sort_key)
    level_value = st.selectbox(
        "Level",
        ["All", *level_options],
        index=0,
        disabled=not bool(level_options),
        key="za_level",
    )

# apply filters to hunts
filtered = norm_df.copy()
if not filtered.empty and voc_value:
    filtered = filtered[filtered["vocation"] == voc_value]
if not filtered.empty and mode_value:
    filtered = filtered[filtered["mode"] == mode_value]
if not filtered.empty and level_value != "All":
    filtered = filtered[filtered["level_bucket"] == level_value]

# aggregate
agg_df = aggregate_by_zone(filtered)
if not agg_df.empty:
    rename_map = {
        "Zona": "Zone",
        "Hunts": "Hunts",
        "Horas": "Hours",
        "XP Gain (media/h)": "XP Gain (avg/h)",
        "Raw XP Gain (media/h)": "Raw XP Gain (avg/h)",
        "Supplies (media/h)": "Supplies (avg/h)",
        "Loot (media/h)": "Loot (avg/h)",
        "Balance (media/h)": "Balance (avg/h)",
    }
    agg_df = agg_df.rename(columns=rename_map)
    for c in ["Supplies (avg/h)", "Loot (avg/h)", "XP Gain (avg/h)"]:
        if c in agg_df.columns:
            agg_df = agg_df.drop(columns=[c])
    if "Raw XP Gain (avg/h)" in agg_df.columns:
        agg_df["Stamina (avg/h)"] = agg_df["Raw XP Gain (avg/h)"] * 1.5
    order_cols = [
        "Zone",
        "Hunts",
        "Hours",
        "Balance (avg/h)",
        "Raw XP Gain (avg/h)",
        "Stamina (avg/h)",
    ]
    agg_df = agg_df[[c for c in order_cols if c in agg_df.columns]]

st.markdown("---")
st.markdown("## Zone Averages")

if agg_df.empty:
    st.table(pd.DataFrame())
    current_df = agg_df
else:
    # sorting controls
    sort_cols = list(agg_df.columns)
    sc1, sc2, _ = st.columns([0.28, 0.28, 0.44])
    with sc1:
        sort_by = st.selectbox("Sort by", options=sort_cols, index=0, key="za_sort_by")
    with sc2:
        order = st.radio("Order", ["Ascending", "Descending"], index=0, horizontal=True, key="za_sort_order")
    ascending = order == "Ascending"

    current_df = agg_df.sort_values(by=sort_by, ascending=ascending, kind="mergesort")

    # header row
    hdr = st.container()
    with hdr:
        c = st.columns([3, 1, 1, 1, 1, 1])
        c[0].markdown("**Zone**")
        c[1].markdown("**Hunts**")
        c[2].markdown("**Hours**")
        c[3].markdown("**Balance (avg/h)**")
        c[4].markdown("**Raw XP Gain (avg/h)**")
        if "Stamina (avg/h)" in current_df.columns:
            c[5].markdown("**Stamina (avg/h)**")
        else:
            c[5].markdown("")

    # rows + expander "More details" under each summary row
    for _, r in current_df.iterrows():
        zone_name = str(r.get("Zone", ""))
        cols = st.columns([3, 1, 1, 1, 1, 1])
        cols[0].write(zone_name)
        cols[1].write(fmt_int(r.get("Hunts", 0)))
        cols[2].write(fmt_hours(r.get("Hours", 0.0)))
        cols[3].write(fmt_int(r.get("Balance (avg/h)", 0)))
        cols[4].write(fmt_int(r.get("Raw XP Gain (avg/h)", 0)))
        if "Stamina (avg/h)" in current_df.columns:
            cols[5].write(fmt_int(r.get("Stamina (avg/h)", 0)))
        else:
            cols[5].write("")

        with st.expander("More details"):
            # raw hunts for this zone and active filters
            zdf = filtered[filtered["zona"] == zone_name].copy()

            # to datetime
            zdf["session_start_dt"] = pd.to_datetime(zdf.get("session_start"), errors="coerce")
            zdf["session_end_dt"] = pd.to_datetime(zdf.get("session_end"), errors="coerce")

            # duration per hunt -> Duration text
            if "duration_sec" in zdf.columns:
                zdf["__hours"] = zdf["duration_sec"].astype(float) / 3600.0
            else:
                zdf["__hours"] = (
                    zdf["session_end_dt"] - zdf["session_start_dt"]
                ).dt.total_seconds() / 3600.0
            zdf["Duration"] = zdf["__hours"].apply(fmt_duration_text)

            # stamina per file
            if "raw_xp_gain" in zdf.columns:
                zdf["Stamina"] = zdf["raw_xp_gain"].astype(float) * 1.5
            else:
                zdf["Stamina"] = 0.0

            cols_out = []
            if "session_start" in zdf.columns:
                cols_out.append("session_start")
            if "session_end" in zdf.columns:
                cols_out.append("session_end")
            cols_out += ["Duration"]
            if "raw_xp_gain" in zdf.columns:
                cols_out.append("raw_xp_gain")
            if "Stamina" in zdf.columns:
                cols_out.append("Stamina")
            if "balance" in zdf.columns:
                cols_out.append("balance")

            # latest 10 hunts
            if "session_end_dt" in zdf.columns:
                zdf = zdf.sort_values(by="session_end_dt", ascending=False)
            elif "session_start_dt" in zdf.columns:
                zdf = zdf.sort_values(by="session_start_dt", ascending=False)

            zdf = zdf[cols_out].head(10).rename(
                columns={
                    "session_start": "Start",
                    "session_end": "End",
                    "raw_xp_gain": "Raw XP Gain",
                    "balance": "Balance",
                }
            )

            st.caption("Last 10 hunts (raw data, no averages)")
            st.table(
                style_center(
                    zdf,
                    {"Raw XP Gain": fmt_int, "Stamina": fmt_int, "Balance": fmt_int},
                    hide_index=True,
                )
            )
        st.divider()

# CSV export of the summary table
csv_bytes = df_to_csv_bytes(
    current_df if current_df is not None and not current_df.empty else pd.DataFrame()
)
st.download_button(
    label="Export CSV",
    data=csv_bytes,
    file_name="tibia_analyzer_aggregated.csv",
    mime="text/csv",
    disabled=current_df is None or current_df.empty,
)
