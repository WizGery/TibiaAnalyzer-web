from __future__ import annotations

def fmt_int(x):
    try:
        if x is None: 
            return ""
        n = int(round(float(x)))
        return f"{n:,}".replace(",", ".")
    except Exception:
        return str(x) if x is not None else ""

def fmt_float(x, ndigits: int = 2):
    try:
        return f"{float(x):.{ndigits}f}"
    except Exception:
        return ""

def fmt_hours_from_seconds(sec):
    try:
        sec = int(float(sec))
        h = sec // 3600
        m = (sec % 3600) // 60
        return f"{h:02d}:{m:02d}h"
    except Exception:
        return ""
