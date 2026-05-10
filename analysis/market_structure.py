from __future__ import annotations

import pandas as pd


def analyze_market_regime(
    df: pd.DataFrame,
    ema_span: int = 20,
    lookback: int = 30,
) -> dict:
    if df.empty or len(df) < max(ema_span, 10):
        return {
            "status": "insufficient_data",
            "structure": "insufficient_data",
            "bias": "NEUTRAL",
            "trend_state": "unknown",
            "range_state": "unknown",
            "breakout_state": "none",
            "close_location": None,
            "range_percent": None,
            "ema_distance_percent": None,
            "ema_slope_percent": None,
            "reason": "Not enough candles to classify market regime.",
        }

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

    full_high = float(recent["high"].max())
    full_low = float(recent["low"].min())
    range_size = full_high - full_low
    avg_price = float(recent["close"].mean())
    range_percent = (range_size / avg_price) * 100 if avg_price > 0 else None
    is_tight_range = range_percent is not None and range_percent < 0.6

    ema_distance_percent = ((last_close - last_ema) / last_ema) * 100 if last_ema > 0 else None
    ema_slope_percent = _ema_slope_percent(recent)
    close_location = _close_location(last_close, full_low, full_high)

    structure = _structure_label(
        last_close=last_close,
        recent_high=recent_high,
        recent_low=recent_low,
        above_ema=above_ema,
        slope_up=slope_up,
        is_tight_range=is_tight_range,
        ema_distance_percent=ema_distance_percent,
    )
    trend_state = _trend_state(above_ema, ema_slope_percent, slope_up)
    range_state = _range_state(range_percent, close_location)
    breakout_state = _breakout_state(last_close, recent_high, recent_low)
    bias = _bias_from_structure(structure)

    return {
        "status": "ok",
        "structure": structure,
        "bias": bias,
        "trend_state": trend_state,
        "range_state": range_state,
        "breakout_state": breakout_state,
        "close_location": close_location,
        "range_percent": _round_optional(range_percent),
        "ema_distance_percent": _round_optional(ema_distance_percent),
        "ema_slope_percent": _round_optional(ema_slope_percent),
        "reason": _regime_reason(structure, trend_state, range_state, breakout_state),
    }


def classify_structure(
    df: pd.DataFrame,
    ema_span: int = 20,
    lookback: int = 30,
) -> str:
    return analyze_market_regime(df, ema_span=ema_span, lookback=lookback)["structure"]


def _structure_label(
    last_close: float,
    recent_high: float,
    recent_low: float,
    above_ema: bool,
    slope_up: bool,
    is_tight_range: bool,
    ema_distance_percent: float | None,
) -> str:
    if last_close > recent_high and above_ema:
        if ema_distance_percent is not None and ema_distance_percent > 0.4:
            return "extended_uptrend"
        return "breakout"

    if last_close < recent_low and not above_ema:
        if ema_distance_percent is not None and ema_distance_percent < -0.4:
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


def _ema_slope_percent(recent: pd.DataFrame, slope_lookback: int = 5) -> float | None:
    if len(recent) <= slope_lookback:
        return None
    latest_ema = float(recent.iloc[-1]["ema"])
    prior_ema = float(recent.iloc[-slope_lookback - 1]["ema"])
    latest_close = float(recent.iloc[-1]["close"])
    if latest_close == 0:
        return None
    return ((latest_ema - prior_ema) / latest_close) * 100


def _close_location(last_close: float, low: float, high: float) -> float | None:
    range_size = high - low
    if range_size <= 0:
        return None
    return round((last_close - low) / range_size, 4)


def _trend_state(above_ema: bool, ema_slope_percent: float | None, slope_up: bool) -> str:
    if ema_slope_percent is None:
        return "unknown"
    if above_ema and ema_slope_percent >= 0.15 and slope_up:
        return "rising"
    if not above_ema and ema_slope_percent <= -0.15 and not slope_up:
        return "falling"
    if abs(ema_slope_percent) < 0.08:
        return "flat"
    if above_ema:
        return "bullish_bias"
    return "bearish_bias"


def _range_state(range_percent: float | None, close_location: float | None) -> str:
    if range_percent is None:
        return "unknown"
    if range_percent < 0.6:
        if close_location is not None and close_location >= 0.7:
            return "compressed_near_highs"
        if close_location is not None and close_location <= 0.3:
            return "compressed_near_lows"
        return "compressed"
    if range_percent > 2.5:
        return "wide"
    return "normal"


def _breakout_state(last_close: float, recent_high: float, recent_low: float) -> str:
    if last_close > recent_high:
        return "upside_breakout"
    if last_close < recent_low:
        return "downside_breakout"
    return "none"


def _bias_from_structure(structure: str) -> str:
    if structure in {"breakout", "uptrend", "bullish_bias", "range_near_highs", "extended_uptrend"}:
        return "BULLISH"
    if structure in {"breakdown", "downtrend", "bearish_bias", "extended_downtrend"}:
        return "BEARISH"
    return "NEUTRAL"


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _regime_reason(
    structure: str,
    trend_state: str,
    range_state: str,
    breakout_state: str,
) -> str:
    return (
        f"Structure is {structure}; trend is {trend_state}; "
        f"range state is {range_state}; breakout state is {breakout_state}."
    )
