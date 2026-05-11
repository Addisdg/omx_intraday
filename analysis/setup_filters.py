from __future__ import annotations

import pandas as pd

from analysis.indicators import calculate_macd, calculate_rsi


BULLISH_PULLBACK_WEIGHTS = {
    "above_sma200": 15,
    "pullback_completed": 20,
    "rsi_recovering": 15,
    "macd_turning_positive": 15,
    "reclaiming_sma50": 15,
    "strong_bullish_candle_near_resistance": 10,
    "reward_risk_before_resistance": 10,
}


def analyze_bullish_pullback_setup(
    df: pd.DataFrame,
    resistance_lookback: int = 20,
    volume_lookback: int = 20,
) -> dict:
    if df is None or df.empty:
        return _empty_result("No candles available for bullish pullback screening.")
    if len(df) < 210:
        return _empty_result("At least 210 candles are needed for SMA200-based screening.")

    work = df.copy()
    work["sma50"] = work["close"].rolling(50, min_periods=50).mean()
    work["sma200"] = work["close"].rolling(200, min_periods=200).mean()
    work["rsi"] = calculate_rsi(work["close"], window=14)
    work = work.join(calculate_macd(work["close"]))
    work["average_volume"] = work["volume"].rolling(volume_lookback, min_periods=1).mean()

    latest = work.iloc[-1]
    previous = work.iloc[-2]
    if pd.isna(latest["sma200"]) or pd.isna(latest["sma50"]) or pd.isna(latest["rsi"]):
        return _empty_result("Indicator warmup is incomplete for bullish pullback screening.")

    price = float(latest["close"])
    sma50 = float(latest["sma50"])
    sma200 = float(latest["sma200"])
    prev_close = float(previous["close"])
    prev_sma50 = float(previous["sma50"])
    resistance = _recent_resistance(work, resistance_lookback)
    stop_loss = _suggested_stop(work, sma50)
    rr_ratio = _reward_risk(price, stop_loss, resistance)

    condition_details = {
        "above_sma200": _condition(
            price > sma200 and _slope(work["sma200"], 10) >= 0,
            f"Close {price:.2f} is above SMA200 {sma200:.2f} with non-falling SMA200 slope.",
        ),
        "pullback_completed": _condition(
            _pullback_completed(work, sma50),
            "Recent pullback reached the SMA50 area and latest candle recovered above SMA50.",
        ),
        "rsi_recovering": _condition(
            _rsi_recovering(work),
            f"RSI14 is recovering at {float(latest['rsi']):.2f}.",
        ),
        "macd_turning_positive": _condition(
            _macd_turning_positive(work),
            f"MACD histogram is turning up at {float(latest['macd_histogram']):.4f}.",
        ),
        "reclaiming_sma50": _condition(
            prev_close <= prev_sma50 and price > sma50,
            f"Close reclaimed SMA50 {sma50:.2f} after the prior close was below/at SMA50.",
        ),
        "strong_bullish_candle_near_resistance": _condition(
            _strong_bullish_candle_near_resistance(work, resistance),
            "Latest candle has a strong body, closes near its high, volume is above average, and price is near resistance.",
        ),
        "reward_risk_before_resistance": _condition(
            rr_ratio is not None and rr_ratio >= 1.5,
            "Estimated reward/risk to nearby resistance is at least 1.5.",
        ),
    }

    score = sum(BULLISH_PULLBACK_WEIGHTS[name] for name, detail in condition_details.items() if detail["passed"])
    passed = [name for name, detail in condition_details.items() if detail["passed"]]
    failed = [name for name, detail in condition_details.items() if not detail["passed"]]

    return {
        "status": "ok",
        "setup": "bullish_pullback_recovery",
        "candidate": score >= 70 and len(failed) <= 2,
        "score": score,
        "max_score": sum(BULLISH_PULLBACK_WEIGHTS.values()),
        "passed_conditions": passed,
        "failed_conditions": failed,
        "conditions": condition_details,
        "price": round(price, 4),
        "sma50": round(sma50, 4),
        "sma200": round(sma200, 4),
        "rsi": round(float(latest["rsi"]), 2),
        "macd_histogram": round(float(latest["macd_histogram"]), 4),
        "relative_volume": _relative_volume(latest),
        "nearest_resistance": None if resistance is None else round(resistance, 4),
        "suggested_stop": None if stop_loss is None else round(stop_loss, 4),
        "rr_to_resistance": None if rr_ratio is None else round(rr_ratio, 2),
        "reason": _reason(score, passed, failed),
    }


def _empty_result(reason: str) -> dict:
    return {
        "status": "insufficient_data",
        "setup": "bullish_pullback_recovery",
        "candidate": False,
        "score": 0,
        "max_score": sum(BULLISH_PULLBACK_WEIGHTS.values()),
        "passed_conditions": [],
        "failed_conditions": list(BULLISH_PULLBACK_WEIGHTS),
        "conditions": {},
        "price": None,
        "sma50": None,
        "sma200": None,
        "rsi": None,
        "macd_histogram": None,
        "relative_volume": None,
        "nearest_resistance": None,
        "suggested_stop": None,
        "rr_to_resistance": None,
        "reason": reason,
    }


def _condition(passed: bool, reason: str) -> dict:
    return {"passed": bool(passed), "reason": reason}


def _slope(series: pd.Series, lookback: int) -> float:
    if len(series) <= lookback or pd.isna(series.iloc[-lookback - 1]):
        return 0.0
    return float(series.iloc[-1] - series.iloc[-lookback - 1])


def _pullback_completed(work: pd.DataFrame, sma50: float) -> bool:
    recent = work.tail(12)
    prior = work.iloc[-13:-1]
    pulled_back = bool((prior["low"] <= sma50 * 1.03).any() or (prior["close"] <= sma50 * 1.02).any())
    latest = recent.iloc[-1]
    previous = recent.iloc[-2]
    recovered = float(latest["close"]) > sma50 and float(latest["close"]) > float(previous["close"])
    return pulled_back and recovered


def _rsi_recovering(work: pd.DataFrame) -> bool:
    rsi = work["rsi"].tail(5)
    if rsi.isna().any():
        return False
    latest = float(rsi.iloc[-1])
    previous = float(rsi.iloc[-2])
    recent_low = float(rsi.min())
    crossed_recovery_zone = previous < 50 <= latest or previous < 40 <= latest
    return latest >= 45 and latest > previous and (crossed_recovery_zone or latest - recent_low >= 5)


def _macd_turning_positive(work: pd.DataFrame) -> bool:
    hist = work["macd_histogram"].tail(4)
    if hist.isna().any():
        return False
    latest = float(hist.iloc[-1])
    previous = float(hist.iloc[-2])
    crossed_positive = previous <= 0 < latest
    rising = latest > previous > float(hist.iloc[-3])
    return crossed_positive or (latest > 0 and rising)


def _recent_resistance(work: pd.DataFrame, lookback: int) -> float | None:
    prior = work.iloc[-lookback - 1 : -1]
    if prior.empty:
        return None
    return float(prior["high"].max())


def _strong_bullish_candle_near_resistance(work: pd.DataFrame, resistance: float | None) -> bool:
    if resistance is None:
        return False
    latest = work.iloc[-1]
    candle_range = float(latest["high"] - latest["low"])
    if candle_range <= 0:
        return False
    body = abs(float(latest["close"] - latest["open"]))
    close_location = (float(latest["close"]) - float(latest["low"])) / candle_range
    bullish = float(latest["close"]) > float(latest["open"])
    relative_volume = _relative_volume(latest)
    distance_to_resistance = abs(float(latest["close"]) - resistance) / resistance if resistance > 0 else 1
    return bullish and body / candle_range >= 0.55 and close_location >= 0.75 and relative_volume >= 1.1 and distance_to_resistance <= 0.03


def _suggested_stop(work: pd.DataFrame, sma50: float) -> float | None:
    recent_low = float(work["low"].tail(10).min())
    price = float(work.iloc[-1]["close"])
    stop = min(recent_low, sma50 * 0.985)
    if stop >= price:
        return None
    return stop


def _reward_risk(price: float, stop_loss: float | None, resistance: float | None) -> float | None:
    if stop_loss is None or resistance is None:
        return None
    risk = price - stop_loss
    reward = resistance - price
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def _relative_volume(latest: pd.Series) -> float:
    average_volume = float(latest.get("average_volume", 0) or 0)
    if average_volume <= 0:
        return 0.0
    return round(float(latest["volume"]) / average_volume, 2)


def _reason(score: int, passed: list[str], failed: list[str]) -> str:
    return (
        f"Bullish pullback score {score}/100 with {len(passed)} conditions passed "
        f"and {len(failed)} conditions still missing."
    )
