from __future__ import annotations

import pandas as pd


def nearest_support(supports: list[float], price: float):
    below = [s for s in supports if s <= price]
    return max(below) if below else None


def nearest_resistance(resistances: list[float], price: float):
    above = [r for r in resistances if r >= price]
    return min(above) if above else None


def detect_signal(
    df: pd.DataFrame,
    supports: list[float],
    resistances: list[float],
) -> dict:
    if len(df) < 2:
        return {"signal": "WAIT", "reason": "Not enough data"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(last["close"])
    ns = nearest_support(supports, price)
    nr = nearest_resistance(resistances, price)

    # breakout
    if nr is not None and float(prev["close"]) <= nr and float(last["close"]) > nr:
        return {
            "signal": "BUY BREAKOUT",
            "reason": f"Close broke above resistance {nr}",
        }

    # breakdown
    if ns is not None and float(prev["close"]) >= ns and float(last["close"]) < ns:
        return {"signal": "SELL BREAKDOWN", "reason": f"Close broke below support {ns}"}

    # fake breakout
    if nr is not None and float(last["high"]) > nr and float(last["close"]) < nr:
        return {
            "signal": "FAKE BREAKOUT",
            "reason": f"Price rejected above resistance {nr}",
        }

    # fake breakdown
    if ns is not None and float(last["low"]) < ns and float(last["close"]) > ns:
        return {"signal": "FAKE BREAKDOWN", "reason": f"Price reclaimed support {ns}"}

    return {"signal": "WAIT", "reason": "No clean trigger"}
