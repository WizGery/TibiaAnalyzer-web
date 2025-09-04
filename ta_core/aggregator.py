# ta_core/aggregator.py
from __future__ import annotations
from typing import Dict, Any, Iterable, List
import pandas as pd


# ============================================================================
# Helpers internos
# ============================================================================

# Columnas candidatas para kills por monstruo (dict/JSON/lista de pares)
_CANDIDATE_KILLS_COLUMNS: tuple[str, ] = (
    "kills_by_monster",
    "killsByMonster",
    "kills_by_creature",
    "creatures_killed",
    "monsters_killed",
    "kills",
    "monsters",
)

def _get_any(row: Any, keys: Iterable[str], default=None):
    """Obtiene el primer valor existente en 'row' para cualquiera de las claves."""
    get = row.get if hasattr(row, "get") else (lambda k, d=None: getattr(row, k, d))
    for k in keys:
        if hasattr(row, "index"):
            # pandas Series
            if k in row.index:
                return get(k, default)
        else:
            v = get(k, default)
            if v is not None:
                return v
    return default


def _parse_as_mapping(val: Any) -> Dict[str, float]:
    """Convierte distintos formatos a {monster: kills_float}."""
    if val is None:
        return {}

    # dict directo
    if isinstance(val, dict):
        out: Dict[str, float] = {}
        for k, v in val.items():
            try:
                out[str(k)] = float(v or 0)
            except Exception:
                continue
        return out

    # string -> intenta JSON o literal
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return {}
        try:
            import json
            obj = json.loads(s)
            return _parse_as_mapping(obj)
        except Exception:
            pass
        try:
            import ast
            obj = ast.literal_eval(s)
            return _parse_as_mapping(obj)
        except Exception:
            return {}

    # lista de pares o de dicts
    if isinstance(val, (list, tuple)):
        out: Dict[str, float] = {}
        for item in val:
            # ["Dragon", 12] ó ("Dragon", 12)
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                name = str(item[0])
                try:
                    out[name] = out.get(name, 0.0) + float(item[1] or 0)
                except Exception:
                    continue
            # {"monster":"Dragon","kills":12} / {"name":"Dragon","count":12}
            elif isinstance(item, dict):
                name_key = None
                for k in ("monster", "name", "creature", "Monster", "Name"):
                    if k in item:
                        name_key = k
                        break
                kills_key = None
                for k in ("kills", "count", "qty", "n", "Count", "Kills"):
                    if k in item:
                        kills_key = k
                        break
                if name_key and kills_key:
                    try:
                        name = str(item[name_key])
                        out[name] = out.get(name, 0.0) + float(item[kills_key] or 0)
                    except Exception:
                        continue
        return out

    return {}


def _extract_kills_mapping_from_row(row: Any) -> Dict[str, float]:
    """Busca kills en distintas columnas y las normaliza a {monster: kills}.

    Soporta explícitamente el formato real de tus sesiones:
    - "Killed Monsters": lista de dicts con {"Name": str, "Count": num}
    """
    get = row.get if hasattr(row, "get") else (lambda k, d=None: getattr(row, k, d))

    # 1) Formato real: "Killed Monsters" (lista de dicts Name/Count)
    for key in ("Killed Monsters", "killed_monsters", "Killed monsters"):
        if hasattr(row, "index"):
            present = key in row.index
        else:
            present = getattr(row, key, None) is not None
        if present:
            val = get(key, None)
            mapping = _parse_as_mapping(val)
            if mapping:
                return mapping

    # 2) Otras columnas candidatas (dict/JSON/lista de pares)
    for col in _CANDIDATE_KILLS_COLUMNS:
        if hasattr(row, "index") and col not in row.index:
            continue
        val = get(col, None)
        mapping = _parse_as_mapping(val)
        if mapping:
            return mapping

    return {}


def _parse_session_length(text: str) -> float:
    """Intenta parsear 'Session length' como horas.
    Admite formatos tipo '00:22h', '1:02h', '1h 2min', '62min'.
    """
    if not text:
        return 0.0
    s = str(text).strip().lower()
    try:
        # 'HH:MMh' → split ':'
        if ":" in s and "h" in s:
            hh, mmh = s.split(":", 1)
            mm = "".join(ch for ch in mmh if ch.isdigit()) or "0"
            return max(0.0, float(int(hh)) + float(int(mm)) / 60.0)
        # '1h 2min'
        if "h" in s:
            parts = s.replace("min", "").split("h")
            H = int(parts[0].strip() or "0")
            M = int(parts[1].strip() or "0") if len(parts) > 1 else 0
            return max(0.0, H + M / 60.0)
        # '62min'
        if "min" in s:
            m = int(s.replace("min", "").strip() or "0")
            return max(0.0, m / 60.0)
    except Exception:
        return 0.0
    return 0.0


def _row_hours_fallback(row) -> float:
    """Devuelve horas de una fila, usando esta prioridad:
       1) duration_sec
       2) __hours
       3) session_start / session_end (o variantes con mayúsculas)
       4) Session length (string)
    """
    get = row.get if hasattr(row, "get") else (lambda k, d=None: getattr(row, k, d))

    # 1) duration_sec
    for key in ("duration_sec", "Duration Sec", "duration"):
        try:
            ds = get(key, None)
            if ds is not None and float(ds) > 0:
                return float(ds) / 3600.0
        except Exception:
            pass

    # 2) __hours
    try:
        hh = get("__hours", None)
        if hh is not None and float(hh) > 0:
            return float(hh)
    except Exception:
        pass

    # 3) session_start / session_end (snake y TibiLog original)
    start = _get_any(row, ("session_start", "Session start"), None)
    end = _get_any(row, ("session_end", "Session end"), None)
    try:
        if start is not None and end is not None:
            s = pd.to_datetime(start, errors="coerce")
            e = pd.to_datetime(end, errors="coerce")
            if pd.notna(s) and pd.notna(e):
                sec = (e - s).total_seconds()
                if sec and sec > 0:
                    return sec / 3600.0
    except Exception:
        pass

    # 4) Session length (string)
    length_txt = _get_any(row, ("Session length", "session_length"), None)
    if isinstance(length_txt, str):
        hrs = _parse_session_length(length_txt)
        if hrs > 0:
            return hrs

    return 0.0


# ============================================================================
# Funciones públicas
# ============================================================================

def aggregate_by_zone(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega métricas por zona y calcula tasas por hora a partir de duration_sec."""
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "Zona", "Hunts", "Horas", "XP Gain (media/h)", "Raw XP Gain (media/h)",
            "Supplies (media/h)", "Loot (media/h)", "Balance (media/h)"
        ])

    df = df.copy()
    # Si no hay duration_sec, este campo quedará NaN; las tasas por hora que usan 'Horas'
    # se basan en 'hours_total' que suma estas horas (pueden ser 0 si faltan).
    if "duration_sec" in df.columns:
        df["hours"] = df["duration_sec"].astype(float) / 3600.0
    else:
        df["hours"] = 0.0

    grp = df.groupby("zona", as_index=False).agg(
        hunts=("path", "count"),
        hours_total=("hours", "sum"),
        xp_gain_total=("xp_gain", "sum"),
        raw_xp_gain_total=("raw_xp_gain", "sum"),
        supplies_total=("supplies", "sum"),
        loot_total=("loot", "sum"),
        balance_total=("balance", "sum"),
    )

    def _safe_div(num, den):
        try:
            return (float(num) / float(den)) if float(den) > 0 else 0.0
        except Exception:
            return 0.0

    grp["xp_gain_per_h"] = grp.apply(lambda r: _safe_div(r["xp_gain_total"], r["hours_total"]), axis=1)
    grp["raw_xp_gain_per_h"] = grp.apply(lambda r: _safe_div(r["raw_xp_gain_total"], r["hours_total"]), axis=1)
    grp["supplies_per_h"] = grp.apply(lambda r: _safe_div(r["supplies_total"], r["hours_total"]), axis=1)
    grp["loot_per_h"] = grp.apply(lambda r: _safe_div(r["loot_total"], r["hours_total"]), axis=1)
    grp["balance_per_h"] = grp.apply(lambda r: _safe_div(r["balance_total"], r["hours_total"]), axis=1)

    out = grp[[
        "zona", "hunts", "hours_total", "xp_gain_per_h", "raw_xp_gain_per_h",
        "supplies_per_h", "loot_per_h", "balance_per_h"
    ]].rename(columns={
        "zona": "Zona",
        "hunts": "Hunts",
        "hours_total": "Horas",
        "xp_gain_per_h": "XP Gain (media/h)",
        "raw_xp_gain_per_h": "Raw XP Gain (media/h)",
        "supplies_per_h": "Supplies (media/h)",
        "loot_per_h": "Loot (media/h)",
        "balance_per_h": "Balance (media/h)",
    }).sort_values(by="Balance (media/h)", ascending=False, kind="stable").reset_index(drop=True)

    for col in ["Horas", "XP Gain (media/h)", "Raw XP Gain (media/h)", "Supplies (media/h)", "Loot (media/h)", "Balance (media/h)"]:
        out[col] = out[col].astype(float).round(2)

    return out


def compute_monsters_kph_for_df(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calcula {monster: KPH} usando TODAS las hunt sessions crudas del DataFrame.
    - Busca kills en "Killed Monsters" (lista de dicts Name/Count) y en varias columnas candidatas.
    - Horas: duration_sec -> __hours -> session_start/end (o variantes) -> Session length (string).
    """
    if df is None or df.empty:
        return {}

    kills_sum: Dict[str, float] = {}
    hours_sum: Dict[str, float] = {}

    for _, row in df.iterrows():
        hours = _row_hours_fallback(row)
        if hours <= 0:
            continue

        km = _extract_kills_mapping_from_row(row)
        if not km:
            continue

        for monster, k in km.items():
            try:
                kf = float(k or 0)
            except Exception:
                continue
            if kf <= 0:
                continue
            kills_sum[monster] = kills_sum.get(monster, 0.0) + kf
            hours_sum[monster] = hours_sum.get(monster, 0.0) + hours

    out: Dict[str, float] = {}
    for m, ksum in kills_sum.items():
        hrs = hours_sum.get(m, 0.0)
        out[m] = round(ksum / hrs, 4) if hrs > 0 else 0.0
    return out
