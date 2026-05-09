from __future__ import annotations

import pandas as pd


def analyze_volatility_regime(
    df: pd.DataFrame,
    atr_window: int = 14,
    history_window: int = 50,
) -> dict:
    if df.empty or len(df) < atr_window + 2:
        return {
            "volatility_state": "insufficient_data",
            "current_atr": None,
            "baseline_atr": None,
            "atr_ratio": None,
            "reason": "Not enough candles to classify volatility regime",
        }

    true_range = _true_range(df)
    atr = true_range.rolling(atr_window, min_periods=atr_window).mean().dropna()
    if len(atr) < 2:
        return {
            "volatility_state": "insufficient_data",
            "current_atr": None,
            "baseline_atr": None,
            "atr_ratio": None,
            "reason": "Not enough ATR history to classify volatility regime",
        }

    current_atr = float(atr.iloc[-1])
    baseline_series = atr.iloc[:-1].tail(history_window)
    baseline_atr = float(baseline_series.median()) if not baseline_series.empty else 0.0

    if baseline_atr <= 0:
        return {
            "volatility_state": "unknown",
            "current_atr": round(current_atr, 4),
            "baseline_atr": round(baseline_atr, 4),
            "atr_ratio": None,
            "reason": "Baseline ATR is unavailable or zero",
        }

    ratio = current_atr / baseline_atr
    state = _state_from_ratio(ratio)
    return {
        "volatility_state": state,
        "current_atr": round(current_atr, 4),
        "baseline_atr": round(baseline_atr, 4),
        "atr_ratio": round(ratio, 2),
        "reason": _reason(state, ratio),
    }


def _true_range(df: pd.DataFrame) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


def _state_from_ratio(ratio: float) -> str:
    if ratio < 0.75:
        return "quiet"
    if ratio <= 1.25:
        return "normal"
    if ratio <= 1.75:
        return "elevated"
    return "extreme"


def _reason(state: str, ratio: float) -> str:
    if state == "quiet":
        return f"Current ATR is quiet versus recent history ({ratio:.2f}x baseline)"
    if state == "normal":
        return f"Current ATR is near its recent baseline ({ratio:.2f}x baseline)"
    if state == "elevated":
        return f"Current ATR is elevated versus recent history ({ratio:.2f}x baseline)"
    return f"Current ATR is extreme versus recent history ({ratio:.2f}x baseline)"

