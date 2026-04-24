from __future__ import annotations

import pandas as pd

from analysis.signals import nearest_resistance, nearest_support
from analysis.trade_engine import TradePlan


BULLISH_STRUCTURES = {"breakout", "uptrend", "bullish_bias", "range_near_highs", "extended_uptrend"}
BEARISH_STRUCTURES = {"breakdown", "downtrend", "bearish_bias", "extended_downtrend"}
ACTIONABLE_SETUPS = {"BUY_BREAKOUT", "BUY_PULLBACK", "SELL_BREAKDOWN", "SELL_RETEST"}


def score_setup(
    df: pd.DataFrame,
    structure: str,
    signal: dict,
    trade_plan: TradePlan,
    supports: list[float],
    resistances: list[float],
    volume_read: dict,
) -> dict:
    if df.empty:
        return {"score": 0, "grade": "No data", "components": {}, "notes": ["No data available"]}

    latest = df.iloc[-1]
    price = float(latest["close"])
    ema20 = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
    score = 0
    components: dict[str, int] = {}
    notes: list[str] = []

    alignment = _score_alignment(price, ema20, structure)
    components["trend_alignment"] = alignment
    score += alignment

    level_score = _score_level_distance(price, supports, resistances)
    components["level_location"] = level_score
    score += level_score

    rr_score = _score_rr(trade_plan.rr_ratio)
    components["reward_risk"] = rr_score
    score += rr_score

    volume_score = _score_volume(volume_read)
    components["volume"] = volume_score
    score += volume_score

    freshness = _score_freshness(signal, trade_plan)
    components["freshness"] = freshness
    score += freshness

    if trade_plan.setup not in ACTIONABLE_SETUPS:
        notes.append("No actionable setup is active; confidence is capped.")
        score = min(score, 55)

    if volume_read.get("volume_state") in {"spike", "above_average"}:
        notes.append(volume_read["reason"])
    if trade_plan.rr_ratio is not None and trade_plan.rr_ratio >= 2:
        notes.append("Reward/risk passes the minimum filter")

    score = max(0, min(100, int(score)))
    return {
        "score": score,
        "grade": _grade(score),
        "components": components,
        "notes": notes or ["No strong confirmation factors detected"],
    }


def _score_alignment(price: float, ema20: float, structure: str) -> int:
    if structure in BULLISH_STRUCTURES and price > ema20:
        return 25
    if structure in BEARISH_STRUCTURES and price < ema20:
        return 25
    if structure in BULLISH_STRUCTURES | BEARISH_STRUCTURES:
        return 10
    return 5


def _score_level_distance(price: float, supports: list[float], resistances: list[float]) -> int:
    levels = [level for level in [nearest_support(supports, price), nearest_resistance(resistances, price)] if level]
    if not levels:
        return 8
    nearest = min(abs(price - level) / price for level in levels if price > 0)
    if nearest <= 0.0015:
        return 18
    if nearest <= 0.004:
        return 13
    return 7


def _score_rr(rr_ratio: float | None) -> int:
    if rr_ratio is None:
        return 0
    if rr_ratio >= 3:
        return 22
    if rr_ratio >= 2:
        return 18
    if rr_ratio >= 1.5:
        return 10
    return 0


def _score_volume(volume_read: dict) -> int:
    state = volume_read.get("volume_state")
    if state == "spike":
        return 20
    if state == "above_average":
        return 15
    if state == "normal":
        return 9
    if state == "quiet":
        return 3
    return 0


def _score_freshness(signal: dict, trade_plan: TradePlan) -> int:
    signal_name = signal.get("signal", "")
    if trade_plan.setup in {"BUY_BREAKOUT", "SELL_BREAKDOWN"}:
        return 15
    if "BREAKOUT" in signal_name or "BREAKDOWN" in signal_name:
        return 15
    if trade_plan.setup in {"BUY_PULLBACK", "SELL_RETEST"}:
        return 10
    return 4


def _grade(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Low"
    return "Very low"
