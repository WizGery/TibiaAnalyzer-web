import pandas as pd

# Agrega por zona y calcula tasas por hora
def aggregate_by_zone(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "Zona", "Hunts", "Horas", "XP Gain (media/h)", "Raw XP Gain (media/h)",
            "Supplies (media/h)", "Loot (media/h)", "Balance (media/h)"
        ])

    df = df.copy()
    df["hours"] = df["duration_sec"] / 3600.0

    grp = df.groupby("zona", as_index=False).agg(
        hunts=("path", "count"),
        hours_total=("hours", "sum"),
        xp_gain_total=("xp_gain", "sum"),
        raw_xp_gain_total=("raw_xp_gain", "sum"),
        supplies_total=("supplies", "sum"),
        loot_total=("loot", "sum"),
        balance_total=("balance", "sum"),
    )

    grp["xp_gain_per_h"] = grp.apply(lambda r: (r["xp_gain_total"] / r["hours_total"]) if r["hours_total"]>0 else 0, axis=1)
    grp["raw_xp_gain_per_h"] = grp.apply(lambda r: (r["raw_xp_gain_total"] / r["hours_total"]) if r["hours_total"]>0 else 0, axis=1)
    grp["supplies_per_h"] = grp.apply(lambda r: (r["supplies_total"] / r["hours_total"]) if r["hours_total"]>0 else 0, axis=1)
    grp["loot_per_h"] = grp.apply(lambda r: (r["loot_total"] / r["hours_total"]) if r["hours_total"]>0 else 0, axis=1)
    grp["balance_per_h"] = grp.apply(lambda r: (r["balance_total"] / r["hours_total"]) if r["hours_total"]>0 else 0, axis=1)

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
    })

    out = out.sort_values(by="Balance (media/h)", ascending=False, kind="stable").reset_index(drop=True)

    for col in ["Horas", "XP Gain (media/h)", "Raw XP Gain (media/h)", "Supplies (media/h)", "Loot (media/h)", "Balance (media/h)"]:
        out[col] = out[col].astype(float).round(2)

    return out