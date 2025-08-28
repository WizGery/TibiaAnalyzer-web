# app_pages/2_Pending.py
from typing import List, Dict, Callable
import re
import json

import pandas as pd
import streamlit as st

from ta_core.normalizer import normalize_records
from ta_core.repository import load_store, save_store

from utils.sidebar import render_global_sidebar  # Global sidebar (Backup + Danger zone)

# ---- Sidebar global on every page ----
with st.sidebar:
    render_global_sidebar()

# ===== CSS (table alignment) =====
st.markdown("""
<style>
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
    """
    Calcula el 'balance real' desde:
      1) Resumen de Party Hunt (con 'Balance:' de sesión y balances por jugador indentados):
         - balance_real_por_persona = Balance_total_sesion / nº_jugadores
      2) Texto de transferencias (paid/sent/received...):
         - suma positiva/negativa según palabras clave.
    """
    lines = text.splitlines()

    def to_int(s: str) -> int:
        s = s.replace(".", "").replace(",", "")
        try:
            return int(s)
        except Exception:
            return 0

    # 1) Intentar formato "Party Hunt" con 'Balance:' de sesión y balances por jugador
    session_total = None
    member_count = 0
    balance_re = re.compile(r"Balance\s*:\s*([-+]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|[-+]?\d+)", re.I)

    for line in lines:
        m = balance_re.search(line)
        if not m:
            continue
        val = to_int(m.group(1))
        indent = len(line) - len(line.lstrip())  # 0 = tope, >0 = indentado (jugador)
        if indent == 0 and session_total is None:
            # Primer 'Balance:' sin indentación -> total de la sesión
            session_total = val
        else:
            # Balances por jugador (indentados)
            member_count += 1

    if session_total is not None:
        divisor = member_count if member_count > 0 else 1
        return int(round(session_total / divisor))

    # 2) Modo transferencias: sumar SOLO líneas con palabras clave (no loot/supplies/damage/healing)
    total = 0
    for line in lines:
        has_pos = bool(TRANSFER_POS_PAT.search(line))
        has_neg = bool(TRANSFER_NEG_PAT.search(line))
        if not (has_pos or has_neg):
            continue  # ignorar líneas normales

        nums = NUMBER_PAT.findall(line)
        if not nums:
            continue
        amount = to_int(nums[0])

        if has_neg and not has_pos:
            total -= amount
        else:
            total += amount

    return total


# ---------- formatting helpers ----------
def fmt_int(val):
    if pd.isna(val): return ""
    try:
        n = round(float(val))
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(val)

def title_monster(name: str) -> str:
    return (str(name).strip().title()) if name else ""

def style_center(df: pd.DataFrame, fmt_map: Dict[str, Callable] | None = None, hide_index: bool = True):
    sty = df.style.set_table_styles([
        {"selector": "th", "props": [("text-align", "center")]},
        {"selector": "td", "props": [("text-align", "center")]},
    ]).set_properties(**{"text-align": "center"})
    if fmt_map: sty = sty.format(fmt_map)
    if hide_index:
        try: sty = sty.hide(axis="index")
        except Exception:
            try: sty = sty.hide_index()
            except Exception: pass
    return sty

# =========================
# Load data
# =========================
store: List[Dict] = load_store()
raw_records: List[Dict] = store
norm_df, pending_df = normalize_records(raw_records)

# ===== Helpers to map store rows =====
def row_key_from_store_item(orig: Dict) -> tuple:
    o_start = str(orig.get("Session start", orig.get("session_start", "")))
    o_end   = str(orig.get("Session end",   orig.get("session_end", "")))
    xo_raw  = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
    try:
        xo = int(xo_raw)
    except Exception:
        xo = 0
    return (o_start, o_end, xo)

# =========================
# Pending editor (only)
# =========================
st.markdown(f"## Pending: {len(pending_df)}")

def top3_monsters(sr: Dict) -> List[str]:
    if isinstance(sr, str):
        try: sr = json.loads(sr)
        except Exception: sr = {}
    if not isinstance(sr, dict): sr = {}
    km = sr.get("Killed Monsters") or sr.get("killed_monsters") or sr.get("monsters") or []
    top = []
    if isinstance(km, list):
        try:
            km_sorted = sorted(km, key=lambda x: int(str(x.get("Count", 0)).replace(",", "")), reverse=True)
        except Exception:
            km_sorted = km
        for m in km_sorted[:3]:
            name = title_monster(m.get("Name") or m.get("name") or "?")
            try: cnt = int(str(m.get("Count", 0)).replace(",", ""))
            except Exception: cnt = 0
            top.append(f"{name} ({fmt_int(cnt)})")
    while len(top) < 3: top.append("")
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

with st.expander("Show/Hide pending", expanded=True):
    if pending_df.empty:
        st.success("No pending records.")
    else:
        st.info("Open a record to edit it. A small table will appear below it.")
        existing_zones = sorted({z for z in norm_df.get("zona", pd.Series(dtype=str)).unique() if str(z).strip()})

        for idx, row in pending_df.reset_index(drop=True).iterrows():
            title = f"Edit: {row.get('path','(no name)')} — {row.get('session_start','')} → {row.get('session_end','')}"
            with st.expander(title):
                row_df = pending_minitable(pending_df.iloc[[idx]]).reset_index(drop=True)
                st.table(style_center(row_df, {"Raw XP Gain": fmt_int, "XP Gain": fmt_int, "Balance": fmt_int}))

                st.markdown("---")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    try: voc_idx = VOCATION_OPTIONS.index(row.get("vocation","Knight"))
                    except ValueError: voc_idx = 0
                    new_voc = st.selectbox("Vocation", VOCATION_OPTIONS, index=voc_idx, key=f"voc_{idx}")
                with c2:
                    try: mode_idx = MODE_OPTIONS.index(row.get("mode","Solo"))
                    except ValueError: mode_idx = 0
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
                    try: lvl_idx = LEVEL_BUCKETS.index(row.get("level_bucket", LEVEL_BUCKETS[0]))
                    except ValueError: lvl_idx = 0
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

                # --- Show "Compute real balance" ONLY if Mode != Solo ---
                if new_mode != "Solo":
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
                else:
                    # Clean up states when switching to Solo
                    st.session_state.pop(f"show_rb_{idx}", None)
                    st.session_state.pop(f"calc_balance_{idx}", None)
                    st.session_state.pop(f"transfer_text_{idx}", None)

                cbtn1, cbtn2, cbtn3 = st.columns([0.34, 0.33, 0.33])
                with cbtn1:
                    if st.button("💾 Save this row", key=f"save_{idx}"):
                        s_start = str(row.get("session_start", ""))
                        s_end = str(row.get("session_end", ""))
                        xp_orig = int(row.get("xp_gain", 0))
                        for orig in store:
                            o_start = str(orig.get("Session start", orig.get("session_start", "")))
                            o_end   = str(orig.get("Session end",   orig.get("session_end", "")))
                            xo_raw  = str(orig.get("XP Gain", orig.get("xp_gain", 0))).replace(",", "")
                            xo      = int(xo_raw) if xo_raw.isdigit() else 0
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
