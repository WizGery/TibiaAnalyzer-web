from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class HuntRecord:
    path: str
    session_start: str
    session_end: str
    duration_sec: int
    xp_gain: int
    raw_xp_gain: int
    supplies: int
    loot: int
    balance: int
    vocation: str
    mode: str
    vocation_duo: str
    zona: str
    has_all_meta: bool
    source_raw: Dict[str, Any]

    # nuevo: identificador de propietario (se rellena en Upload_JSON, se cuenta al finalizar en Pending)
    owner_user_id: Optional[str] = None


@dataclass
class AggregatedZone:
    zona: str
    hunts: int
    hours_total: float
    xp_gain_per_h: float
    raw_xp_gain_per_h: float
    supplies_per_h: float
    loot_per_h: float
    balance_per_h: float
