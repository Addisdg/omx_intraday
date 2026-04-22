from __future__ import annotations

import pandas as pd


def nearest_support(supports: list[float], price: float):
    below = [s for s in supports if s <= price]
    return max(below) if below else None


def nearest_resistance(resistances: list[float], price: float):
    above = [r for r in resistances if r >= price]
    return min(above) if above else None


def classify_signal(
    df: pd.DataFrame,
    supports: list[float],
    resistances: list[float],
    structure: str,
    ema_span: int = 20,
) -> dict:
    if df.empty or len(df) < 5:
        return {
            "signal": "WAIT",
            "reason": "Not enough data",
            "nearest_support": None,
            "nearest_resistance": None,
        }

    work = df.copy()
    work["ema20"] = work["close"].ewm(span=ema_span).mean()

    last = work.iloc[-1]
    prev = work.iloc[-2]

    price = float(last["close"])
    ema = float(last["ema20"])

    ns = nearest_support(supports, price)
    nr = nearest_resistance(resistances, price)

    price_above_all_resistance = nr is None and len(resistances) > 0
    price_below_all_support = ns is None and len(supports) > 0

    # Fresh breakout
    if nr is not None and float(prev["close"]) <= nr and price > nr:
        return {
            "signal": "BUY BREAKOUT",
            "reason": f"Close broke above resistance {nr}",
            "nearest_support": ns,
            "nearest_resistance": nr,
        }

    # Fresh breakdown
    if ns is not None and float(prev["close"]) >= ns and price < ns:
        return {
            "signal": "SELL BREAKDOWN",
            "reason": f"Close broke below support {ns}",
            "nearest_support": ns,
            "nearest_resistance": nr,
        }

    # Fake breakout
    if nr is not None and float(last["high"]) > nr and price < nr:
        return {
            "signal": "FAKE BREAKOUT",
            "reason": f"Price rejected back below resistance {nr}",
            "nearest_support": ns,
            "nearest_resistance": nr,
        }

    # Fake breakdown
    if ns is not None and float(last["low"]) < ns and price > ns:
        return {
            "signal": "FAKE BREAKDOWN",
            "reason": f"Price reclaimed support {ns}",
            "nearest_support": ns,
            "nearest_resistance": nr,
        }

    # Higher-level bias logic
    if structure in {"breakout", "uptrend", "bullish_bias", "range_near_highs"}:
        if price > ema:
            if price_above_all_resistance:
                return {
                    "signal": "BULLISH BIAS",
                    "reason": "Price is above EMA and above all detected resistance; wait for pullback or new base",
                    "nearest_support": ns,
                    "nearest_resistance": None,
                }
            return {
                "signal": "WAIT FOR PULLBACK",
                "reason": "Bullish structure, but no fresh breakout trigger",
                "nearest_support": ns,
                "nearest_resistance": nr,
            }

    if structure in {"breakdown", "downtrend", "bearish_bias"}:
        if price < ema:
            if price_below_all_support:
                return {
                    "signal": "BEARISH BIAS",
                    "reason": "Price is below EMA and below all detected support; wait for bounce into resistance",
                    "nearest_support": None,
                    "nearest_resistance": nr,
                }
            return {
                "signal": "WAIT FOR RETEST",
                "reason": "Bearish structure, but no fresh breakdown trigger",
                "nearest_support": ns,
                "nearest_resistance": nr,
            }

    return {
        "signal": "WAIT",
        "reason": "No clean trigger",
        "nearest_support": ns,
        "nearest_resistance": nr,
    }