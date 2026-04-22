from __future__ import annotations

import pandas as pd


def classify_structure(
    df: pd.DataFrame,
    ema_span: int = 20,
    lookback: int = 30,
) -> str:
    if df.empty or len(df) < max(ema_span, 10):
        return "insufficient_data"

    recent = df.tail(min(lookback, len(df))).copy()
    recent["ema"] = recent["close"].ewm(span=ema_span).mean()

    last_close = float(recent.iloc[-1]["close"])
    prev_close = float(recent.iloc[-2]["close"])
    last_ema = float(recent.iloc[-1]["ema"])

    highs = recent["high"].tolist()
    lows = recent["low"].tolist()

    recent_high = max(highs[:-1]) if len(highs) > 1 else highs[-1]
    recent_low = min(lows[:-1]) if len(lows) > 1 else lows[-1]

    slope_up = last_close > prev_close
    above_ema = last_close > last_ema

    range_size = float(recent["high"].max() - recent["low"].min())
    avg_price = float(recent["close"].mean())
    is_tight_range = avg_price > 0 and (range_size / avg_price) < 0.006

    if last_close > recent_high and above_ema:
        if (last_close - last_ema) / last_ema > 0.004:
            return "extended_uptrend"
        return "breakout"

    if last_close < recent_low and not above_ema:
        if (last_ema - last_close) / last_ema > 0.004:
            return "extended_downtrend"
        return "breakdown"

    if is_tight_range:
        if above_ema:
            return "range_near_highs"
        return "range"

    if above_ema and slope_up:
        return "uptrend"

    if (not above_ema) and (not slope_up):
        return "downtrend"

    if above_ema:
        return "bullish_bias"

    return "bearish_bias"