# app_pages/4_Statistics.py
from __future__ import annotations
import pandas as pd
import streamlit as st
import altair as alt

from ta_core.repository import ensure_data_dirs, load_store
from ta_core.normalizer import normalize_records
from utils.sidebar import render_global_sidebar

# ── Sidebar global ──
with st.sidebar:
    render_global_sidebar()

# ── Helpers ──
def fmt_int(val) -> str:
    try:
        n = int(round(float(val or 0)))
        return f"{n:,}".replace(",", ".")
    except Exception:
        return "0"

def fmt_duration_hm(hours_float: float) -> str:
    total_min = int(round((hours_float or 0) * 60))
    h, m = divmod(total_min, 60)
    if h and m: return f"{h}h {m}min"
    if h:       return f"{h}h"
    return f"{m}min"

def level_key(s: str) -> int:
    # Ordena "26-50", "51-75", "101-150", etc.
    try:
        s = str(s)
        left = s.split("-")[0].strip()
        return int(left)
    except Exception:
        return 10**9  # al final

def donut_chart(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    domain: list[str] | None = None,
    colors: list[str] | None = None,
    scheme: str | None = None,
    tooltip_text_col: str | None = None,  # para horas en "h min"
) -> alt.Chart:
    # Color + leyenda sin título
    color_kwargs = {"legend": alt.Legend(title=None)}
    if domain is not None and colors is not None:
        color_kwargs["scale"] = alt.Scale(domain=domain, range=colors)
    elif domain is not None and scheme is not None:
        color_kwargs["scale"] = alt.Scale(domain=domain, scheme=scheme)
    elif colors is not None:
        color_kwargs["scale"] = alt.Scale(range=colors)
    elif scheme is not None:
        color_kwargs["scale"] = alt.Scale(scheme=scheme)

    enc_color = alt.Color(f"{label_col}:N", **color_kwargs)

    # Tooltip: si se pide texto (HoursHM), lo usamos en vez del número
    if tooltip_text_col:
        value_tooltip = alt.Tooltip(f"{tooltip_text_col}:N", title=value_col)
    else:
        value_tooltip = alt.Tooltip(
            f"{value_col}:Q",
            title=value_col,
            format=",.2f" if value_col == "Hours" else ",d",
        )

    return (
        alt.Chart(df, title=title)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta(f"{value_col}:Q"),
            color=enc_color,
            tooltip=[
                alt.Tooltip(f"{label_col}:N", title=""),
                value_tooltip,
                alt.Tooltip("pct:Q", title="Share", format=".1%"),
            ],
        )
        .properties(height=260)
    )

# Paletas fijas
VOCATIONS   = ["Knight", "Paladin", "Druid", "Sorcerer", "Monk"]
VOC_COLORS  = ["#4E79A7", "#59A14F", "#F28E2B", "#EDC948", "#E15759"]
MODES       = ["Solo", "Duo", "TH"]
MODE_COLORS = ["#4E79A7", "#59A14F", "#E15759"]

# ── Datos base ──
ensure_data_dirs()
store = load_store()
norm_df, _ = normalize_records(store)

st.title("Statistics")

if norm_df.empty:
    st.info("No processed data yet.")
    st.stop()

# Totales
total_hunts  = len(norm_df)
total_hours  = (norm_df["duration_sec"].sum() / 3600.0) if "duration_sec" in norm_df.columns else 0.0
total_places = norm_df["zona"].nunique() if "zona" in norm_df.columns else 0

# ======= HUNTS =======
# By vocation
voc_hunts = (
    norm_df["vocation"].value_counts().reindex(VOCATIONS, fill_value=0).astype(int)
    if "vocation" in norm_df.columns else pd.Series([0]*len(VOCATIONS), index=VOCATIONS, dtype=int)
)
hunts_voc_df = pd.DataFrame({"Label": voc_hunts.index, "Hunts": voc_hunts.values})
hunts_voc_df["pct"] = hunts_voc_df["Hunts"] / max(int(hunts_voc_df["Hunts"].sum()), 1)

# By mode
mode_hunts = (
    norm_df["mode"].value_counts().reindex(MODES, fill_value=0).astype(int)
    if "mode" in norm_df.columns else pd.Series([0]*len(MODES), index=MODES, dtype=int)
)
hunts_mode_df = pd.DataFrame({"Label": mode_hunts.index, "Hunts": mode_hunts.values})
hunts_mode_df["pct"] = hunts_mode_df["Hunts"] / max(int(hunts_mode_df["Hunts"].sum()), 1)

# By level bucket (ordenado por límite inferior)
levels_present = sorted(
    [str(x) for x in norm_df.get("level_bucket", pd.Series(dtype=str)).dropna().unique()],
    key=level_key
)
level_hunts = (
    norm_df["level_bucket"].value_counts().reindex(levels_present, fill_value=0).astype(int)
    if "level_bucket" in norm_df.columns else pd.Series(dtype=int)
)
hunts_lvl_df = pd.DataFrame({"Label": level_hunts.index if not level_hunts.empty else [], "Hunts": level_hunts.values if not level_hunts.empty else []})
if not hunts_lvl_df.empty:
    hunts_lvl_df["pct"] = hunts_lvl_df["Hunts"] / max(int(hunts_lvl_df["Hunts"].sum()), 1)

# ======= HOURS =======
# By vocation
voc_hours = (
    norm_df.groupby("vocation")["duration_sec"].sum().div(3600.0).reindex(VOCATIONS, fill_value=0.0)
    if {"vocation","duration_sec"}.issubset(norm_df.columns) else pd.Series([0.0]*len(VOCATIONS), index=VOCATIONS, dtype=float)
)
hours_voc_df = pd.DataFrame({"Label": voc_hours.index, "Hours": voc_hours.values})
hours_voc_df["HoursHM"] = hours_voc_df["Hours"].apply(fmt_duration_hm)
hours_voc_df["pct"] = hours_voc_df["Hours"] / max(float(hours_voc_df["Hours"].sum()), 1.0)

# By mode
mode_hours = (
    norm_df.groupby("mode")["duration_sec"].sum().div(3600.0).reindex(MODES, fill_value=0.0)
    if {"mode","duration_sec"}.issubset(norm_df.columns) else pd.Series([0.0]*len(MODES), index=MODES, dtype=float)
)
hours_mode_df = pd.DataFrame({"Label": mode_hours.index, "Hours": mode_hours.values})
hours_mode_df["HoursHM"] = hours_mode_df["Hours"].apply(fmt_duration_hm)
hours_mode_df["pct"] = hours_mode_df["Hours"] / max(float(hours_mode_df["Hours"].sum()), 1.0)

# By level bucket
level_hours = (
    norm_df.groupby("level_bucket")["duration_sec"].sum().div(3600.0).reindex(levels_present, fill_value=0.0)
    if {"level_bucket","duration_sec"}.issubset(norm_df.columns) else pd.Series(dtype=float)
)
hours_lvl_df = pd.DataFrame({"Label": level_hours.index if not level_hours.empty else [], "Hours": level_hours.values if not level_hours.empty else []})
if not hours_lvl_df.empty:
    hours_lvl_df["HoursHM"] = hours_lvl_df["Hours"].apply(fmt_duration_hm)
    hours_lvl_df["pct"] = hours_lvl_df["Hours"] / max(float(hours_lvl_df["Hours"].sum()), 1.0)

# ======= HUNT PLACES (zonas únicas) =======
# By vocation
voc_places = (
    norm_df.dropna(subset=["zona"]).groupby("vocation")["zona"].nunique().reindex(VOCATIONS, fill_value=0).astype(int)
    if {"vocation","zona"}.issubset(norm_df.columns) else pd.Series([0]*len(VOCATIONS), index=VOCATIONS, dtype=int)
)
places_voc_df = pd.DataFrame({"Label": voc_places.index, "Places": voc_places.values})
places_voc_df["pct"] = places_voc_df["Places"] / max(int(places_voc_df["Places"].sum()), 1)

# By mode
mode_places = (
    norm_df.dropna(subset=["zona"]).groupby("mode")["zona"].nunique().reindex(MODES, fill_value=0).astype(int)
    if {"mode","zona"}.issubset(norm_df.columns) else pd.Series([0]*len(MODES), index=MODES, dtype=int)
)
places_mode_df = pd.DataFrame({"Label": mode_places.index, "Places": mode_places.values})
places_mode_df["pct"] = places_mode_df["Places"] / max(int(places_mode_df["Places"].sum()), 1)

# By level bucket
level_places = (
    norm_df.dropna(subset=["zona"]).groupby("level_bucket")["zona"].nunique().reindex(levels_present, fill_value=0).astype(int)
    if {"level_bucket","zona"}.issubset(norm_df.columns) else pd.Series(dtype=int)
)
places_lvl_df = pd.DataFrame({"Label": level_places.index if not level_places.empty else [], "Places": level_places.values if not level_places.empty else []})
if not places_lvl_df.empty:
    places_lvl_df["pct"] = places_lvl_df["Places"] / max(int(places_lvl_df["Places"].sum()), 1)

# ──────────────────────────────────────────────────────────────────────────────
# SECTION: Total Hunts
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;margin-bottom:0;'>Total Hunts</h2>", unsafe_allow_html=True)
st.markdown(
    f"<div style='text-align:center;font-size:40px;font-weight:700;margin:6px 0 16px 0;'>{fmt_int(total_hunts)}</div>",
    unsafe_allow_html=True,
)

hc1, hc2, hc3 = st.columns(3)
with hc1:
    st.altair_chart(
        donut_chart(hunts_voc_df, "Label", "Hunts", "Hunts by Vocation",
                    domain=VOCATIONS, colors=VOC_COLORS),
        use_container_width=True)
with hc2:
    st.altair_chart(
        donut_chart(hunts_mode_df, "Label", "Hunts", "Hunts by Mode",
                    domain=MODES, colors=MODE_COLORS),
        use_container_width=True)
with hc3:
    st.altair_chart(
        donut_chart(hunts_lvl_df, "Label", "Hunts", "Hunts by Level",
                    domain=levels_present if levels_present else None,
                    scheme="tableau20"),
        use_container_width=True)

st.markdown("---")

# ──────────────────────────────────────────────────────────────────────────────
# SECTION: Total Hours
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;margin-bottom:0;'>Total Hours</h2>", unsafe_allow_html=True)
st.markdown(
    f"<div style='text-align:center;font-size:40px;font-weight:700;margin:6px 0 16px 0;'>{fmt_duration_hm(total_hours)}</div>",
    unsafe_allow_html=True,
)

hc1, hc2, hc3 = st.columns(3)
with hc1:
    st.altair_chart(
        donut_chart(hours_voc_df, "Label", "Hours", "Hours by Vocation",
                    domain=VOCATIONS, colors=VOC_COLORS,
                    tooltip_text_col="HoursHM"),
        use_container_width=True)
with hc2:
    st.altair_chart(
        donut_chart(hours_mode_df, "Label", "Hours", "Hours by Mode",
                    domain=MODES, colors=MODE_COLORS,
                    tooltip_text_col="HoursHM"),
        use_container_width=True)
with hc3:
    st.altair_chart(
        donut_chart(hours_lvl_df, "Label", "Hours", "Hours by Level",
                    domain=levels_present if levels_present else None,
                    scheme="tableau20",
                    tooltip_text_col="HoursHM"),
        use_container_width=True)

st.markdown("---")

# ──────────────────────────────────────────────────────────────────────────────
# SECTION: Total Hunt Places
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<h2 style='text-align:center;margin-bottom:0;'>Total Hunt Places</h2>", unsafe_allow_html=True)
st.markdown(
    f"<div style='text-align:center;font-size:40px;font-weight:700;margin:6px 0 16px 0;'>{fmt_int(total_places)}</div>",
    unsafe_allow_html=True,
)

hc1, hc2, hc3 = st.columns(3)
with hc1:
    st.altair_chart(
        donut_chart(places_voc_df, "Label", "Places", "Hunt Places by Vocation",
                    domain=VOCATIONS, colors=VOC_COLORS),
        use_container_width=True)
with hc2:
    st.altair_chart(
        donut_chart(places_mode_df, "Label", "Places", "Hunt Places by Mode",
                    domain=MODES, colors=MODE_COLORS),
        use_container_width=True)
with hc3:
    st.altair_chart(
        donut_chart(places_lvl_df, "Label", "Places", "Hunt Places by Level",
                    domain=levels_present if levels_present else None,
                    scheme="tableau20"),
        use_container_width=True)
