from __future__ import annotations

import pandas as pd


def analyze_volume(df: pd.DataFrame, lookback: int = 20) -> dict:
    if df.empty or "volume" not in df:
        return {
            "latest_volume": None,
            "average_volume": None,
            "relative_volume": None,
            "volume_state": "unknown",
            "reason": "No volume data available",
        }

    work = df.tail(max(lookback, 2)).copy()
    latest_volume = float(work.iloc[-1]["volume"])
    prior = work.iloc[:-1]["volume"]
    average_volume = float(prior.mean()) if not prior.empty else latest_volume
    relative_volume = latest_volume / average_volume if average_volume > 0 else None

    if relative_volume is None:
        volume_state = "unknown"
        reason = "Average volume is zero"
    elif relative_volume >= 2.0:
        volume_state = "spike"
        reason = "Volume is more than 2x the recent average"
    elif relative_volume >= 1.25:
        volume_state = "above_average"
        reason = "Volume is above the recent average"
    elif relative_volume <= 0.65:
        volume_state = "quiet"
        reason = "Volume is below the recent average"
    else:
        volume_state = "normal"
        reason = "Volume is near the recent average"

    return {
        "latest_volume": round(latest_volume, 2),
        "average_volume": round(average_volume, 2),
        "relative_volume": round(relative_volume, 2) if relative_volume is not None else None,
        "volume_state": volume_state,
        "reason": reason,
    }
