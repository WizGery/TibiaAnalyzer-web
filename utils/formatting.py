# utils/formatting.py
def fmt_hours(h: float | None) -> str:
    if h is None:
        return "—"
    if h == 0:
        return "0h"
    # Si h >= 1: hh:mm ; si h < 1: mm min
    total_min = int(round(h * 60))
    hh, mm = divmod(total_min, 60)
    return f"{hh}h {mm:02d}m" if hh > 0 else f"{mm}min"
