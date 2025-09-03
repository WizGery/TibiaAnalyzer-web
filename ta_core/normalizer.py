import re
from typing import Dict, List, Tuple, Any

import pandas as pd
from dateutil import parser as dt

NUM_COMMAS = re.compile(r"[,.]")
DUR_HMH = re.compile(r"^(\d{1,2}):(\d{2})h$", re.IGNORECASE)

REQ_FIELDS = [
    "path","session_start","session_end","duration","xp_gain","raw_xp_gain",
    "supplies","loot","vocation","mode","zona","level"
]

ALIASES: Dict[str, List[str]] = {
    "session_start": ["Session start", "session_start", "Start", "start"],
    "session_end":   ["Session end", "session_end", "End", "end"],
    "duration":      ["Session length", "duration", "Duration", "length"],
    "xp_gain":       ["XP Gain", "xp_gain", "XP", "Xp Gain"],
    "raw_xp_gain":   ["Raw XP Gain", "raw_xp_gain", "Raw XP"],
    "supplies":      ["Supplies", "supplies"],
    "loot":          ["Loot", "loot"],
    "balance":       ["Balance", "balance"],
    "balance_real":  ["Balance Real", "balance_real", "Real Balance"],
    "transfer_text": ["Transfer", "transfer", "Party Text", "party_text"],
    "vocation":      ["vocation", "Vocation"],
    "mode":          ["mode", "Mode"],
    "vocation_duo":  ["vocation_duo", "Vocation Duo", "Vocation duo"],
    "zona":          ["zona", "Zona", "Zone", "Hunt Place", "Area"],
    "path":          ["path", "Path"],
    "level":         ["Level", "level"]
}

# ---------- helpers internos ----------
def _first_key(d: Dict[str, Any], keys: List[str]):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None

def _get(rec: Dict[str, Any], field: str):
    return _first_key(rec, ALIASES.get(field, [field]))

def _to_int(v) -> int:
    if v is None:
        return 0
    if isinstance(v, int):
        return int(v)
    s = str(v).strip()
    s = NUM_COMMAS.sub("", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9-]", "", s)
    return int(s) if s else 0

def _duration_to_sec(v) -> int:
    if v is None:
        return 0
    if isinstance(v, int):
        return int(v)
    s = str(v).strip()
    m = DUR_HMH.match(s)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        return hh * 3600 + mm * 60
    try:
        return int(s)
    except Exception:
        return 0

# --- helpers: Killed Monsters -> mapping ---
def _km_list_to_mapping(val) -> Dict[str, float]:
    """
    Convierte la lista de dicts [{'Name': ..., 'Count': ...}, ...]
    a {'Monster Name': count, ...}. Acepta string JSON o literal.
    """
    out: Dict[str, float] = {}
    if val is None:
        return out
    if isinstance(val, str):
        try:
            import json
            val = json.loads(val)
        except Exception:
            try:
                import ast
                val = ast.literal_eval(val)
            except Exception:
                return out
    if isinstance(val, (list, tuple)):
        for item in val:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or item.get("name") or "").strip()
            try:
                cnt = float(item.get("Count") or item.get("count") or 0)
            except Exception:
                cnt = 0
            if name:
                out[name] = out.get(name, 0.0) + cnt
    elif isinstance(val, dict):
        # ya viene como mapping
        for k, v in val.items():
            try:
                out[str(k)] = float(v or 0)
            except Exception:
                continue
    return out

def _extract_kills_from_raw(rec: Dict[str, Any]) -> Dict[str, float]:
    """
    Extrae kills por monstruo desde el registro crudo:
    - 'Killed Monsters' (lista Name/Count)
    - 'killed_monsters' (lista)
    - 'kills_by_monster' (mapping)
    """
    if not isinstance(rec, dict):
        return {}
    if "Killed Monsters" in rec:
        return _km_list_to_mapping(rec.get("Killed Monsters"))
    if "killed_monsters" in rec:
        return _km_list_to_mapping(rec.get("killed_monsters"))
    if "kills_by_monster" in rec:
        return _km_list_to_mapping(rec.get("kills_by_monster"))
    return {}

# ---------- normalizador ----------
def normalize_records(raw_records: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows: List[Dict[str, Any]] = []
    pendings: List[Dict[str, Any]] = []

    for r in raw_records:
        rec: Dict[str, Any] = {k: r.get(k) for k in set().union(r.keys(), REQ_FIELDS)}

        session_start = _get(rec, "session_start")
        session_end   = _get(rec, "session_end")
        duration      = _get(rec, "duration")

        xp_gain     = _to_int(_get(rec, "xp_gain"))
        raw_xp_gain = _to_int(_get(rec, "raw_xp_gain"))
        supplies    = _to_int(_get(rec, "supplies"))
        loot        = _to_int(_get(rec, "loot"))
        balance     = _to_int(_get(rec, "balance"))

        # check if Balance Real exists
        balance_real = _to_int(_get(rec, "balance_real"))
        if balance_real:
            balance = balance_real

        vocation     = str(_get(rec, "vocation") or "")
        mode         = str(_get(rec, "mode") or "")
        vocation_duo = str(_get(rec, "vocation_duo") or ("none" if mode.lower()=="solo" else ""))
        zona         = str(_get(rec, "zona") or "")
        path         = str(_get(rec, "path") or "")

        level_raw = _get(rec, "level")
        level_bucket = str(level_raw or "").strip()
        level_min = None
        level_max = None
        if level_bucket:
            m = re.match(r"^(\d+)\s*-(\d+)$", level_bucket)
            if m:
                level_min, level_max = int(m.group(1)), int(m.group(2))
            else:
                try:
                    n = int(re.sub(r"[^0-9]", "", level_bucket))
                    level_min = n
                    level_max = n
                    level_bucket = str(n)
                except Exception:
                    pass

        duration_sec = _duration_to_sec(duration)
        if not duration_sec:
            try:
                start = dt.parse(str(session_start)) if session_start else None
                end = dt.parse(str(session_end)) if session_end else None
                duration_sec = int((end - start).total_seconds()) if end and start else 0
            except Exception:
                duration_sec = 0

        if balance == 0 and (loot or supplies):
            balance = loot - supplies

        transfer_text = str(_get(rec, "transfer_text") or "").strip()

        has_meta = bool(vocation and mode and zona and (xp_gain is not None) and (raw_xp_gain is not None))

        # rule: Duo/TH need balance_real OR transfer text
        if has_meta and mode.lower() in ("duo", "th"):
            has_real = bool(balance_real) or bool(transfer_text)
            has_meta = has_meta and has_real

        row = dict(
            path=path,
            session_start=str(session_start or ""),
            session_end=str(session_end or ""),
            duration_sec=int(duration_sec),
            xp_gain=int(xp_gain),
            raw_xp_gain=int(raw_xp_gain),
            supplies=int(supplies),
            loot=int(loot),
            balance=int(balance),
            vocation=vocation,
            mode=mode,
            vocation_duo=vocation_duo,
            zona=zona,
            has_all_meta=has_meta,
            source_raw=r,  # guardamos el crudo para extraer kills luego
            level_bucket=level_bucket,
            level_min=level_min if level_min is not None else -1,
            level_max=level_max if level_max is not None else -1,
        )

        if not has_meta or not row["zona"] or row["duration_sec"] <= 0:
            pendings.append(row)
        else:
            rows.append(row)

    df = pd.DataFrame(rows)
    pending_df = pd.DataFrame(pendings)

    if not df.empty:
        for col in ["xp_gain","raw_xp_gain","supplies","loot","balance","duration_sec","level_min","level_max"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        for col in ["vocation","mode","vocation_duo","zona","level_bucket"]:
            df[col] = df[col].astype(str)
        # ---- NUEVO: crea kills_by_monster desde el raw ----
        if "kills_by_monster" not in df.columns or df["kills_by_monster"].isna().all():
            df["kills_by_monster"] = df.get("source_raw", pd.Series([{}]*len(df))).apply(_extract_kills_from_raw)

    if not pending_df.empty:
        for col in ["xp_gain","raw_xp_gain","supplies","loot","balance","duration_sec","level_min","level_max"]:
            pending_df[col] = pd.to_numeric(pending_df[col], errors="coerce").fillna(0).astype(int)
        for col in ["vocation","mode","vocation_duo","zona","level_bucket"]:
            pending_df[col] = pending_df[col].astype(str)
        # ---- NUEVO: también en pendings (por consistencia) ----
        if "kills_by_monster" not in pending_df.columns or pending_df["kills_by_monster"].isna().all():
            pending_df["kills_by_monster"] = pending_df.get("source_raw", pd.Series([{}]*len(pending_df))).apply(_extract_kills_from_raw)

    return df, pending_df
