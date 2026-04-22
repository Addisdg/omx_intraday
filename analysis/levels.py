from __future__ import annotations

import pandas as pd


def find_levels(
    df: pd.DataFrame,
    window: int = 3,
    tolerance: float = 0.3,
    min_touches: int = 2,
    recent_only: int = 100,
):
    if df.empty:
        return {"supports": [], "resistances": []}

    work = df.tail(recent_only).copy()

    highs = []
    lows = []

    for i in range(window, len(work) - window):
        high = work.iloc[i]["high"]
        low = work.iloc[i]["low"]

        if high == max(work.iloc[i - window : i + window + 1]["high"]):
            highs.append(high)

        if low == min(work.iloc[i - window : i + window + 1]["low"]):
            lows.append(low)

    def cluster_levels(levels):
        clusters = []

        for lvl in sorted(levels):
            placed = False
            for cluster in clusters:
                if abs(cluster[0] - lvl) <= tolerance:
                    cluster.append(lvl)
                    placed = True
                    break
            if not placed:
                clusters.append([lvl])

        return [sum(c) / len(c) for c in clusters if len(c) >= min_touches]

    supports = cluster_levels(lows)
    resistances = cluster_levels(highs)

    current_price = float(work.iloc[-1]["close"])

    supports = [s for s in supports if s < current_price * 1.01]
    resistances = [r for r in resistances if r > current_price * 0.99]

    supports = [float(s) for s in supports]
    resistances = [float(r) for r in resistances]

    supports = sorted(round(s, 2) for s in supports)
    resistances = sorted(round(r, 2) for r in resistances)

    return {
        "supports": supports,
        "resistances": resistances,
    }