# ta_core/bestiary.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

# Requisitos oficiales por dificultad para "final detail stage"
DIFF_TO_REQ = {
    "Harmless": 25,
    "Trivial": 250,
    "Easy": 500,
    "Medium": 1000,
    "Hard": 2500,
    "Challenging": 5000,
}

VALID_DIFFS = set(DIFF_TO_REQ.keys())

@dataclass
class BestiaryInfo:
    monster: str
    difficulty: Optional[str]               # Puede ser None si no sabemos la dificultad
    required_kills: Optional[int]           # Derivado de difficulty
    current_kills: int                      # Progreso del jugador (0 si no se sabe)
    kph: float                              # Kills/hora dentro de esa zona (tu métrica)
    hours_to_complete: Optional[float]      # ETA = (required - current)/kph

def normalize_diff(diff: Optional[str]) -> Optional[str]:
    if not diff:
        return None
    d = diff.strip().capitalize()
    # Acepta variantes en minúsculas/mayúsculas
    for v in VALID_DIFFS:
        if v.lower() == d.lower():
            return v
    return None

def required_kills_for_diff(diff: Optional[str]) -> Optional[int]:
    d = normalize_diff(diff)
    return DIFF_TO_REQ.get(d) if d else None

def compute_eta(required: Optional[int], current: int, kph: float) -> Optional[float]:
    if required is None or kph <= 0:
        return None
    remain = max(0, required - max(0, current))
    return remain / kph if remain > 0 else 0.0

def make_bestiary_row(
    monster: str,
    kph: float,
    difficulty: Optional[str],
    current_kills: int = 0
) -> BestiaryInfo:
    req = required_kills_for_diff(difficulty)
    eta = compute_eta(req, current_kills, kph)
    return BestiaryInfo(
        monster=monster,
        difficulty=normalize_diff(difficulty),
        required_kills=req,
        current_kills=current_kills,
        kph=kph,
        hours_to_complete=eta,
    )

def compute_zone_bestiary(
    # {monster_name: kph_en_esa_zona}
    monsters_kph: Dict[str, float],
    # {monster_name: dificultad} — puedes rellenar desde un CSV/JSON local o tu repo de datos
    monster_difficulty: Dict[str, str],
    # Progreso actual del jugador (opcional). Si no lo tienes aún, deja {}
    monster_progress: Optional[Dict[str, int]] = None,
) -> Dict[str, BestiaryInfo]:
    monster_progress = monster_progress or {}
    out: Dict[str, BestiaryInfo] = {}
    for m, kph in monsters_kph.items():
        diff = monster_difficulty.get(m)
        curr = int(monster_progress.get(m, 0))
        out[m] = make_bestiary_row(m, kph, diff, curr)
    return out
