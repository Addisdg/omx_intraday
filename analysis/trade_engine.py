from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class TradePlan:
    bias: str
    setup: str
    entry: Optional[float]
    stop_loss: Optional[float]
    target: Optional[float]
    risk_per_share: Optional[float]
    reward_per_share: Optional[float]
    rr_ratio: Optional[float]
    position_size_shares: Optional[int]
    position_size_value: Optional[float]
    reason: str


def nearest_support(supports: list[float], price: float) -> Optional[float]:
    below = [s for s in supports if s <= price]
    return max(below) if below else None


def nearest_resistance(resistances: list[float], price: float) -> Optional[float]:
    above = [r for r in resistances if r >= price]
    return min(above) if above else None


def calculate_position_size(
    portfolio_size_sek: float,
    risk_percent: float,
    entry: float,
    stop_loss: float,
) -> tuple[Optional[int], Optional[float], Optional[float]]:
    risk_amount = portfolio_size_sek * (risk_percent / 100.0)
    risk_per_share = abs(entry - stop_loss)

    if risk_per_share <= 0:
        return None, None, None

    shares = int(risk_amount // risk_per_share)
    value = shares * entry
    return shares, value, risk_per_share


def build_trade_plan(
    df: pd.DataFrame,
    structure: str,
    supports: list[float],
    resistances: list[float],
    portfolio_size_sek: float = 30000,
    risk_percent: float = 1.0,
) -> TradePlan:
    if df.empty or len(df) < 5:
        return TradePlan(
            bias="NEUTRAL",
            setup="NONE",
            entry=None,
            stop_loss=None,
            target=None,
            risk_per_share=None,
            reward_per_share=None,
            rr_ratio=None,
            position_size_shares=None,
            position_size_value=None,
            reason="Not enough data",
        )

    work = df.copy()
    work["ema20"] = work["close"].ewm(span=20).mean()

    last = work.iloc[-1]
    price = float(last["close"])
    ema20 = float(last["ema20"])

    ns = nearest_support(supports, price)
    nr = nearest_resistance(resistances, price)

    # ---------- LONG SETUP ----------
    if structure in {"breakout", "uptrend", "bullish_bias", "range_near_highs"}:
        # If above EMA and support exists, prefer pullback entry near support/EMA
        if price > ema20 and ns is not None:
            entry = max(ns, round(ema20, 2))
            atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
            stop = ns - atr * 0.8
            target = round(price + 2 * (entry - stop), 2)

            shares, value, risk_per_share = calculate_position_size(
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                entry=entry,
                stop_loss=stop,
            )

            reward_per_share = target - entry
            rr_ratio = reward_per_share / risk_per_share if risk_per_share else None

        # 🚨 R/R filter
        if rr_ratio is None or rr_ratio < 2:
            return TradePlan(
                bias="NEUTRAL",
                setup="SKIP",
                entry=None,
                stop_loss=None,
                target=None,
                risk_per_share=None,
                reward_per_share=None,
                rr_ratio=rr_ratio,
                position_size_shares=None,
                position_size_value=None,
                reason=f"R/R too low ({round(rr_ratio, 2) if rr_ratio else 'N/A'})",
            )

        # Breakout continuation
        if nr is not None and price > nr:
            entry = round(price, 2)
            stop = round(nr - 0.3, 2)
            target = round(entry + 2 * (entry - stop), 2)

            shares, value, risk_per_share = calculate_position_size(
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                entry=entry,
                stop_loss=stop,
            )

            reward_per_share = target - entry
            rr_ratio = reward_per_share / risk_per_share if risk_per_share else None

            return TradePlan(
                bias="BULLISH",
                setup="BUY_BREAKOUT",
                entry=entry,
                stop_loss=stop,
                target=target,
                risk_per_share=round(risk_per_share, 2) if risk_per_share else None,
                reward_per_share=round(reward_per_share, 2),
                rr_ratio=round(rr_ratio, 2) if rr_ratio else None,
                position_size_shares=shares,
                position_size_value=round(value, 2) if value else None,
                reason="Bullish breakout above resistance",
            )

    # ---------- SHORT SETUP ----------
    if structure in {"breakdown", "downtrend", "bearish_bias", "extended_downtrend"}:
        if price < ema20 and nr is not None:
            entry = min(nr, round(ema20, 2))
            stop = round(nr + 0.3, 2)
            target = round(price - 2 * (stop - entry), 2)

            shares, value, risk_per_share = calculate_position_size(
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                entry=entry,
                stop_loss=stop,
            )

            reward_per_share = entry - target
            rr_ratio = reward_per_share / risk_per_share if risk_per_share else None

            return TradePlan(
                bias="BEARISH",
                setup="SELL_RETEST",
                entry=round(entry, 2),
                stop_loss=stop,
                target=target,
                risk_per_share=round(risk_per_share, 2) if risk_per_share else None,
                reward_per_share=round(reward_per_share, 2),
                rr_ratio=round(rr_ratio, 2) if rr_ratio else None,
                position_size_shares=shares,
                position_size_value=round(value, 2) if value else None,
                reason="Bearish structure; prefer short on retest into resistance/EMA20",
            )

        if ns is not None and price < ns:
            entry = round(price, 2)
            stop = round(ns + 0.3, 2)
            target = round(entry - 2 * (stop - entry), 2)

            shares, value, risk_per_share = calculate_position_size(
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                entry=entry,
                stop_loss=stop,
            )

            reward_per_share = entry - target
            rr_ratio = reward_per_share / risk_per_share if risk_per_share else None

            return TradePlan(
                bias="BEARISH",
                setup="SELL_BREAKDOWN",
                entry=entry,
                stop_loss=stop,
                target=target,
                risk_per_share=round(risk_per_share, 2) if risk_per_share else None,
                reward_per_share=round(reward_per_share, 2),
                rr_ratio=round(rr_ratio, 2) if rr_ratio else None,
                position_size_shares=shares,
                position_size_value=round(value, 2) if value else None,
                reason="Bearish breakdown below support",
            )

    return TradePlan(
        bias="NEUTRAL",
        setup="WAIT",
        entry=None,
        stop_loss=None,
        target=None,
        risk_per_share=None,
        reward_per_share=None,
        rr_ratio=None,
        position_size_shares=None,
        position_size_value=None,
        reason="No clean trade setup right now",
    )