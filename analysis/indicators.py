from __future__ import annotations

import pandas as pd


def add_indicators(
    df: pd.DataFrame,
    ema_spans: list[int] | None = None,
    include_vwap: bool = True,
    include_atr_bands: bool = True,
    atr_window: int = 14,
    atr_multiplier: float = 1.0,
) -> pd.DataFrame:
    work = df.copy()
    ema_spans = ema_spans or [20]

    for span in ema_spans:
        work[f"ema{span}"] = work["close"].ewm(span=span, adjust=False).mean()

    if include_vwap:
        typical_price = (work["high"] + work["low"] + work["close"]) / 3
        cumulative_volume = work["volume"].replace(0, pd.NA).fillna(0).cumsum()
        cumulative_value = (typical_price * work["volume"]).cumsum()
        work["vwap"] = cumulative_value / cumulative_volume.replace(0, pd.NA)

    if include_atr_bands:
        high_low = work["high"] - work["low"]
        high_close = (work["high"] - work["close"].shift()).abs()
        low_close = (work["low"] - work["close"].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        work["atr"] = true_range.rolling(atr_window, min_periods=1).mean()
        base = work.get("ema20", work["close"])
        work["atr_upper"] = base + work["atr"] * atr_multiplier
        work["atr_lower"] = base - work["atr"] * atr_multiplier

    return work
