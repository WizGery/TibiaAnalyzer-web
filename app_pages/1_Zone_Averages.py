from __future__ import annotations
from typing import List, Dict, Callable
import re
import os
import pandas as pd
import streamlit as st

from ta_core.repository import load_store
from ta_core.normalizer import normalize_records
from ta_core.aggregator import aggregate_by_zone, compute_monsters_kph_for_df
from ta_core.export import df_to_csv_bytes

from utils.tibiawiki import get_monster_icon_pair  # usamos par (data_uri, src_url)

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

def make_level_buckets(buckets: list[tuple[int, int]]) -> list[dict]:
    result = []
    for (start, end) in buckets:
        label = f"{start}–{end}"
        result.append({"label": label, "min": start, "max": end})
    return result

def make_fixed_size_buckets(start: int, end: int, size: int) -> list[dict]:
    buckets = []
    current = start
    while current <= end:
        upper = min(current + size, end)
        label = f"{current}–{upper}"
        buckets.append({"label": label, "min": current, "max": upper})
        current = upper + 1
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

# ---------- Bestiary helpers ----------
_BESTIARY_REQ = {
    "Harmless": 25,
    "Trivial": 250,
    "Easy": 500,
    "Medium": 1000,
    "Hard": 2500,
    "Challenging": 5000,
}

def _norm_diff(diff: str | None) -> str | None:
    if not diff:
        return None
    d = str(diff).strip()
    for k in _BESTIARY_REQ.keys():
        if d.lower() == k.lower():
            return k
    return None

def _req_for_diff(diff: str | None) -> int | None:
    d = _norm_diff(diff)
    return _BESTIARY_REQ.get(d) if d else None

def _fmt_eta_hours(h: float | None) -> str:
    if h is None:
        return "—"
    if h <= 0:
        return "0h"
    mins = int(round(h * 60))
    H, M = divmod(mins, 60)
    return f"{H}h {M:02d}m" if H > 0 else f"{M}min"

@st.cache_data(show_spinner=False)
def load_bestiary_lookup() -> Dict[str, str]:
    candidates = [
        os.path.join("data", "monster_difficulty.csv"),
        os.path.join("ta_core", "bestiary", "monster_difficulty.csv"),
        "monster_difficulty.csv",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                lut: Dict[str, str] = {}
                for _, r in df.iterrows():
                    m = str(r.get("monster", "")).strip()
                    d = str(r.get("difficulty", "")).strip()
                    if m and d:
                        lut[m.lower()] = d
                return lut
            except Exception:
                pass
    return {}

BESTIARY_LUT = load_bestiary_lookup()

# ---------- data ----------
st.title("Zone Averages")
store = load_store()
norm_df, pending_df = normalize_records(store)

LEVEL_BUCKETS = []

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
    sort_cols = list(agg_df.columns)
    sc1, sc2, _ = st.columns([0.28, 0.28, 0.44])
    with sc1:
        sort_by = st.selectbox("Sort by", options=sort_cols, index=0, key="za_sort_by")
    with sc2:
        order = st.radio("Order", ["Ascending", "Descending"], index=0, horizontal=True, key="za_sort_order")
    ascending = order == "Ascending"

    current_df = agg_df.sort_values(by=sort_by, ascending=ascending, kind="mergesort")

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
            zdf = filtered[filtered["zona"] == zone_name].copy()
            zdf["session_start_dt"] = pd.to_datetime(zdf.get("session_start"), errors="coerce")
            zdf["session_end_dt"] = pd.to_datetime(zdf.get("session_end"), errors="coerce")

            if "duration_sec" in zdf.columns:
                zdf["__hours"] = zdf["duration_sec"].astype(float) / 3600.0
            else:
                zdf["__hours"] = (
                    zdf["session_end_dt"] - zdf["session_start_dt"]
                ).dt.total_seconds() / 3600.0
            zdf["Duration"] = zdf["__hours"].apply(fmt_duration_text)

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

            st.markdown("---")
            st.markdown("#### 📘 Bestiary — time to complete (ETA)")

            zone_all = filtered[filtered["zona"] == zone_name].copy()
            monsters_kph: Dict[str, float] = compute_monsters_kph_for_df(zone_all)

            if not monsters_kph:
                st.info("No **KPH per monster** data in this zone yet.")
            else:
                rows_eta = []
                for monster, kph in monsters_kph.items():
                    name_lc = str(monster).lower().strip()
                    diff = BESTIARY_LUT.get(name_lc)
                    req = _req_for_diff(diff)
                    eta_h = None
                    if req is not None and kph > 0:
                        eta_h = float(req) / float(kph)

                    data_uri, src_url = get_monster_icon_pair(monster)

                    rows_eta.append({
                        "data_uri": data_uri,
                        "src_url": src_url or "",
                        "Monster": monster,
                        "KPH": round(float(kph), 2),
                        "ETA": _fmt_eta_hours(eta_h),
                    })

                def _sort_key(row: Dict) -> tuple:
                    eta = row.get("ETA", "—")
                    if eta == "—":
                        return (1, 10**9, row["Monster"].lower())
                    txt = str(eta)
                    mins = 0
                    if "h" in txt:
                        try:
                            parts = txt.replace("min", "").split("h")
                            H = int(parts[0].strip())
                            M = int(parts[1].strip()) if parts[1].strip() else 0
                            mins = H * 60 + M
                        except Exception:
                            mins = 10**8
                    else:
                        try:
                            mins = int(txt.replace("min", "").strip())
                        except Exception:
                            mins = 10**8
                    return (0, mins, row["Monster"].lower())

                rows_eta_sorted = sorted(rows_eta, key=_sort_key)

                st.markdown(
                    """
                    <div style="display:grid;grid-template-columns:auto 120px 120px;gap:0.5rem;
                                padding:6px 8px;font-weight:600;border-bottom:1px solid rgba(255,255,255,0.08);">
                      <div>Monster</div>
                      <div style="text-align:right;">KPH</div>
                      <div style="text-align:right;">ETA</div>
                    </div>
                    """, unsafe_allow_html=True)

                rows_html = []
                for row in rows_eta_sorted:
                    if row["data_uri"]:
                        icon_box = (
                            f'<div style="width:48px;height:48px;border-radius:8px;overflow:hidden;'
                            f'display:inline-flex;align-items:center;justify-content:center;'
                            f'background:rgba(255,255,255,0.04);flex:0 0 auto;">'
                            f'  <img src="{row["data_uri"]}" title="{row["src_url"]}" '
                            f'       style="width:100%;height:100%;object-fit:contain;'
                            f'              image-rendering:pixelated;display:block;">'
                            f'</div>'
                        )
                    else:
                        icon_box = (
                            '<div style="width:48px;height:48px;border-radius:8px;overflow:hidden;'
                            'display:inline-flex;align-items:center;justify-content:center;'
                            'background:rgba(255,255,255,0.04);flex:0 0 auto;" title="(no image)">🖼️</div>'
                        )

                    monster_cell = (
                        f'<div style="display:flex;align-items:center;gap:10px;">'
                        f'  {icon_box}'
                        f'  <span style="line-height:48px;">{row["Monster"]}</span>'
                        f'</div>'
                    )

                    rows_html.append(
                        f'''
                        <div style="display:grid;grid-template-columns:auto 120px 120px;gap:0.5rem;
                                    padding:10px 8px;border-bottom:1px solid rgba(255,255,255,0.04);">
                          <div>{monster_cell}</div>
                          <div style="text-align:right;">{fmt_int(row["KPH"])}</div>
                          <div style="text-align:right;">{row["ETA"]}</div>
                        </div>
                        '''
                    )

                st.markdown("".join(rows_html), unsafe_allow_html=True)

        st.divider()

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
