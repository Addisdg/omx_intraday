from __future__ import annotations

import pandas as pd


def find_levels(
    df: pd.DataFrame,
    window: int = 3,
    tolerance: float = 1.5,
    min_touches: int = 2,
) -> dict[str, list[float]]:
    if len(df) < (window * 2 + 1):
        return {"supports": [], "resistances": []}

    low_candidates: list[float] = []
    high_candidates: list[float] = []

    for i in range(window, len(df) - window):
        section = df.iloc[i - window : i + window + 1]

        low = float(df.iloc[i]["low"])
        high = float(df.iloc[i]["high"])

        if low == float(section["low"].min()):
            low_candidates.append(low)
        if high == float(section["high"].max()):
            high_candidates.append(high)

    def cluster(vals: list[float]) -> list[float]:
        vals = sorted(vals)
        if not vals:
            return []

        groups: list[list[float]] = [[vals[0]]]
        for v in vals[1:]:
            center = sum(groups[-1]) / len(groups[-1])
            if abs(v - center) <= tolerance:
                groups[-1].append(v)
            else:
                groups.append([v])

        return [
            round(sum(g) / len(g), 2)
            for g in groups
            if len(g) >= min_touches
        ]

    return {
        "supports": cluster(low_candidates),
        "resistances": cluster(high_candidates),
    }