from __future__ import annotations

import pandas as pd


def add_indicators(
    df: pd.DataFrame,
    ema_spans: list[int] | None = None,
    include_vwap: bool = True,
    include_atr_bands: bool = True,
    atr_window: int = 14,
    atr_multiplier: float = 1.0,
    include_rsi: bool = False,
    include_macd: bool = False,
    include_bollinger: bool = False,
    rsi_window: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bollinger_window: int = 20,
    bollinger_std: float = 2.0,
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

    if include_rsi:
        work["rsi"] = calculate_rsi(work["close"], window=rsi_window)

    if include_macd:
        macd = calculate_macd(work["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal)
        work = work.join(macd)

    if include_bollinger:
        bands = calculate_bollinger_bands(
            work["close"],
            window=bollinger_window,
            std_multiplier=bollinger_std,
        )
        work = work.join(bands)

    return work


def calculate_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.rolling(window, min_periods=window).mean()
    average_loss = losses.rolling(window, min_periods=window).mean()
    rs = average_gain / average_loss.where(average_loss != 0)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100)
    rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50)
    return rsi


def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_histogram": histogram,
        },
        index=close.index,
    )


def calculate_bollinger_bands(
    close: pd.Series,
    window: int = 20,
    std_multiplier: float = 2.0,
) -> pd.DataFrame:
    middle = close.rolling(window, min_periods=window).mean()
    std = close.rolling(window, min_periods=window).std(ddof=0)
    upper = middle + std * std_multiplier
    lower = middle - std * std_multiplier
    band_width = upper - lower
    percent_b = (close - lower) / band_width.where(band_width != 0)
    return pd.DataFrame(
        {
            "bb_middle": middle,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_percent_b": percent_b,
        },
        index=close.index,
    )


def summarize_indicator_context(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "status": "no_data",
            "rsi": None,
            "rsi_state": "unknown",
            "macd": None,
            "macd_signal": None,
            "macd_histogram": None,
            "macd_state": "unknown",
            "bollinger_percent_b": None,
            "bollinger_state": "unknown",
            "trend_strength_state": "unknown",
            "ema20_slope_percent": None,
            "reason": "No candles are available for indicator context.",
        }

    enriched = add_indicators(
        df,
        ema_spans=[20],
        include_vwap=False,
        include_atr_bands=False,
        include_rsi=True,
        include_macd=True,
        include_bollinger=True,
    )
    latest = enriched.iloc[-1]
    rsi = _clean_float(latest.get("rsi"))
    macd = _clean_float(latest.get("macd"))
    macd_signal = _clean_float(latest.get("macd_signal"))
    macd_histogram = _clean_float(latest.get("macd_histogram"))
    percent_b = _clean_float(latest.get("bb_percent_b"))
    trend_strength = _trend_strength(enriched)

    if rsi is None:
        return {
            "status": "insufficient_data",
            "rsi": None,
            "rsi_state": "unknown",
            "macd": _round_optional(macd),
            "macd_signal": _round_optional(macd_signal),
            "macd_histogram": _round_optional(macd_histogram),
            "macd_state": _macd_state(macd_histogram),
            "bollinger_percent_b": _round_optional(percent_b),
            "bollinger_state": _bollinger_state(percent_b),
            "trend_strength_state": trend_strength["state"],
            "ema20_slope_percent": trend_strength["slope_percent"],
            "reason": "Not enough candles are available for a full RSI/Bollinger context.",
        }

    rsi_state = _rsi_state(rsi)
    macd_state = _macd_state(macd_histogram)
    bollinger_state = _bollinger_state(percent_b)
    reason = _indicator_reason(rsi_state, macd_state, bollinger_state, trend_strength["state"])

    return {
        "status": "ok",
        "rsi": round(rsi, 2),
        "rsi_state": rsi_state,
        "macd": _round_optional(macd),
        "macd_signal": _round_optional(macd_signal),
        "macd_histogram": _round_optional(macd_histogram),
        "macd_state": macd_state,
        "bollinger_percent_b": _round_optional(percent_b),
        "bollinger_state": bollinger_state,
        "trend_strength_state": trend_strength["state"],
        "ema20_slope_percent": trend_strength["slope_percent"],
        "reason": reason,
    }


def _clean_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _rsi_state(rsi: float) -> str:
    if rsi >= 70:
        return "overbought"
    if rsi <= 30:
        return "oversold"
    return "neutral"


def _macd_state(histogram: float | None) -> str:
    if histogram is None:
        return "unknown"
    if histogram > 0:
        return "bullish"
    if histogram < 0:
        return "bearish"
    return "neutral"


def _bollinger_state(percent_b: float | None) -> str:
    if percent_b is None:
        return "unknown"
    if percent_b > 1:
        return "above_upper"
    if percent_b >= 0.8:
        return "near_upper"
    if percent_b < 0:
        return "below_lower"
    if percent_b <= 0.2:
        return "near_lower"
    return "inside"


def _trend_strength(enriched: pd.DataFrame, lookback: int = 5) -> dict:
    if len(enriched) <= lookback or "ema20" not in enriched:
        return {"state": "unknown", "slope_percent": None}
    latest_ema = _clean_float(enriched.iloc[-1].get("ema20"))
    prior_ema = _clean_float(enriched.iloc[-lookback - 1].get("ema20"))
    latest_close = _clean_float(enriched.iloc[-1].get("close"))
    if latest_ema is None or prior_ema is None or latest_close in {None, 0}:
        return {"state": "unknown", "slope_percent": None}
    slope_percent = ((latest_ema - prior_ema) / latest_close) * 100
    if slope_percent >= 0.5:
        state = "strengthening_up"
    elif slope_percent <= -0.5:
        state = "strengthening_down"
    else:
        state = "flat"
    return {"state": state, "slope_percent": round(slope_percent, 4)}


def _indicator_reason(
    rsi_state: str,
    macd_state: str,
    bollinger_state: str,
    trend_strength_state: str,
) -> str:
    parts = [
        f"RSI is {rsi_state}",
        f"MACD momentum is {macd_state}",
        f"Bollinger position is {bollinger_state}",
        f"EMA20 slope is {trend_strength_state}",
    ]
    return "; ".join(parts) + "."
