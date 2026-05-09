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
        return {
            "score": 0,
            "grade": "No data",
            "components": {},
            "factors": {},
            "max_score": 100,
            "cap_applied": False,
            "raw_score": 0,
            "notes": ["No data available"],
        }

    latest = df.iloc[-1]
    price = float(latest["close"])
    ema20 = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
    notes: list[str] = []
    factors = {
        "trend_alignment": _factor_alignment(price, ema20, structure),
        "level_location": _factor_level_distance(price, supports, resistances),
        "reward_risk": _factor_rr(trade_plan.rr_ratio),
        "volume": _factor_volume(volume_read),
        "freshness": _factor_freshness(signal, trade_plan),
    }

    components = {name: factor["score"] for name, factor in factors.items()}
    raw_score = sum(components.values())
    score = raw_score
    cap_applied = False

    if trade_plan.setup not in ACTIONABLE_SETUPS:
        notes.append("No actionable setup is active; confidence is capped.")
        score = min(score, 55)
        cap_applied = raw_score > score

    if volume_read.get("volume_state") in {"spike", "above_average"}:
        notes.append(volume_read["reason"])
    if trade_plan.rr_ratio is not None and trade_plan.rr_ratio >= 2:
        notes.append("Reward/risk passes the minimum filter")

    score = max(0, min(100, int(score)))
    return {
        "score": score,
        "grade": _grade(score),
        "components": components,
        "factors": factors,
        "max_score": 100,
        "cap_applied": cap_applied,
        "raw_score": raw_score,
        "notes": notes or ["No strong confirmation factors detected"],
    }


def _factor_alignment(price: float, ema20: float, structure: str) -> dict:
    if structure in BULLISH_STRUCTURES and price > ema20:
        return _factor(25, 25, f"Bullish structure and price is above EMA20 ({ema20:.2f})")
    if structure in BEARISH_STRUCTURES and price < ema20:
        return _factor(25, 25, f"Bearish structure and price is below EMA20 ({ema20:.2f})")
    if structure in BULLISH_STRUCTURES | BEARISH_STRUCTURES:
        return _factor(10, 25, f"{structure} structure is present, but price is not aligned with EMA20")
    return _factor(5, 25, "Market structure is neutral or unclear")


def _factor_level_distance(price: float, supports: list[float], resistances: list[float]) -> dict:
    levels = [level for level in [nearest_support(supports, price), nearest_resistance(resistances, price)] if level]
    if not levels:
        return _factor(8, 18, "No nearby support or resistance was detected")
    nearest = min(abs(price - level) / price for level in levels if price > 0)
    if nearest <= 0.0015:
        return _factor(18, 18, "Price is very close to a detected support/resistance level")
    if nearest <= 0.004:
        return _factor(13, 18, "Price is moderately close to a detected support/resistance level")
    return _factor(7, 18, "Price is not close to the nearest detected support/resistance level")


def _factor_rr(rr_ratio: float | None) -> dict:
    if rr_ratio is None:
        return _factor(0, 22, "No active trade plan with a reward/risk ratio")
    if rr_ratio >= 3:
        return _factor(22, 22, f"Reward/risk is strong at {rr_ratio:.2f}")
    if rr_ratio >= 2:
        return _factor(18, 22, f"Reward/risk passes the minimum filter at {rr_ratio:.2f}")
    if rr_ratio >= 1.5:
        return _factor(10, 22, f"Reward/risk is marginal at {rr_ratio:.2f}")
    return _factor(0, 22, f"Reward/risk is below the minimum filter at {rr_ratio:.2f}")


def _factor_volume(volume_read: dict) -> dict:
    state = volume_read.get("volume_state")
    if state == "spike":
        return _factor(20, 20, volume_read.get("reason", "Volume spike confirms participation"))
    if state == "above_average":
        return _factor(15, 20, volume_read.get("reason", "Above-average volume supports the setup"))
    if state == "normal":
        return _factor(9, 20, volume_read.get("reason", "Volume is normal"))
    if state == "quiet":
        return _factor(3, 20, volume_read.get("reason", "Quiet volume weakens confirmation"))
    return _factor(0, 20, "Volume confirmation is unavailable")


def _factor_freshness(signal: dict, trade_plan: TradePlan) -> dict:
    signal_name = signal.get("signal", "")
    if trade_plan.setup in {"BUY_BREAKOUT", "SELL_BREAKDOWN"}:
        return _factor(15, 15, "Trade plan is based on a fresh breakout/breakdown")
    if "BREAKOUT" in signal_name or "BREAKDOWN" in signal_name:
        return _factor(15, 15, f"Signal is fresh: {signal_name}")
    if trade_plan.setup in {"BUY_PULLBACK", "SELL_RETEST"}:
        return _factor(10, 15, "Trade plan is based on a pullback/retest scenario")
    return _factor(4, 15, "No fresh actionable trigger is active")


def _factor(score: int, max_score: int, reason: str) -> dict:
    return {"score": score, "max_score": max_score, "reason": reason}


def _grade(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Low"
    return "Very low"
