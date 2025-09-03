# ta_core/bestiary_data.py
import csv
from pathlib import Path
from typing import Dict

DATA_PATHS = [
    Path("data/monster_difficulty.csv"),
    Path("./data/monster_difficulty.csv"),
]

def load_monster_difficulty() -> Dict[str, str]:
    for p in DATA_PATHS:
        if p.exists():
            d: Dict[str, str] = {}
            with p.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    m = (row.get("monster") or "").strip()
                    diff = (row.get("difficulty") or "").strip()
                    if m and diff:
                        d[m] = diff
            return d
    return {}
