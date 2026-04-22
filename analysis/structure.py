from __future__ import annotations

import pandas as pd


def classify_structure(df: pd.DataFrame, lookback: int = 20) -> str:
    if len(df) < lookback:
        return "insufficient_data"

    recent = df.tail(lookback)
    first_close = float(recent.iloc[0]["close"])
    last_close = float(recent.iloc[-1]["close"])

    highest = float(recent["high"].max())
    lowest = float(recent["low"].min())

    if last_close >= highest * 0.999:
        return "bullish_breakout"
    if last_close <= lowest * 1.001:
        return "bearish_breakdown"

    move_pct = abs(last_close - first_close) / first_close
    if move_pct < 0.003:
        return "range"

    return "uptrend" if last_close > first_close else "downtrend"


def fake_breakout_above(df: pd.DataFrame, level: float, candles: int = 3) -> bool:
    recent = df.tail(candles)
    return bool((recent["high"] > level).any() and recent.iloc[-1]["close"] < level)


def fake_breakdown_below(df: pd.DataFrame, level: float, candles: int = 3) -> bool:
    recent = df.tail(candles)
    return bool((recent["low"] < level).any() and recent.iloc[-1]["close"] > level)
