from __future__ import annotations

import pandas as pd


def classify_structure(df: pd.DataFrame, lookback: int = 20) -> str:
    if df.empty or len(df) < 5:
        return "insufficient_data"

    recent = df.tail(min(lookback, len(df))).copy()

    first_close = float(recent.iloc[0]["close"])
    last_close = float(recent.iloc[-1]["close"])
    highest = float(recent["high"].max())
    lowest = float(recent["low"].min())

    if last_close >= highest * 0.999:
        return "bullish_breakout"
    if last_close <= lowest * 1.001:
        return "bearish_breakdown"

    move_pct = abs(last_close - first_close) / first_close if first_close else 0.0
    if move_pct < 0.003:
        return "range"

    return "uptrend" if last_close > first_close else "downtrend"
