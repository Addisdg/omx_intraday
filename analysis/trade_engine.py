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

    risk_limited_shares = int(risk_amount // risk_per_share)
    buying_power_shares = int(portfolio_size_sek // entry) if entry > 0 else 0
    shares = min(risk_limited_shares, buying_power_shares)
    value = shares * entry
    return shares, value, risk_per_share


def _empty_plan(
    setup: str = "WAIT", reason: str = "No clean trade setup right now"
) -> TradePlan:
    return TradePlan(
        bias="NEUTRAL",
        setup=setup,
        entry=None,
        stop_loss=None,
        target=None,
        risk_per_share=None,
        reward_per_share=None,
        rr_ratio=None,
        position_size_shares=None,
        position_size_value=None,
        reason=reason,
    )


def _finalize_plan(
    bias: str,
    setup: str,
    entry: float,
    stop_loss: float,
    target: float,
    portfolio_size_sek: float,
    risk_percent: float,
    reason: str,
    min_rr: float = 2.0,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
) -> TradePlan:
    adjusted_entry = entry + slippage_points if bias == "BULLISH" else entry - slippage_points
    adjusted_stop = stop_loss
    adjusted_target = target - slippage_points if bias == "BULLISH" else target + slippage_points
    shares, value, risk_per_share = calculate_position_size(
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        entry=adjusted_entry,
        stop_loss=adjusted_stop,
    )

    if risk_per_share is None:
        return _empty_plan(setup="SKIP", reason="Invalid risk: entry and stop are equal")

    fee_per_share = fee_per_trade / shares if shares else 0.0
    reward_per_share = (
        adjusted_target - adjusted_entry
        if bias == "BULLISH"
        else adjusted_entry - adjusted_target
    )
    reward_per_share -= fee_per_share
    rr_ratio = reward_per_share / risk_per_share if risk_per_share else None

    if rr_ratio is None or rr_ratio < min_rr:
        return TradePlan(
            bias="NEUTRAL",
            setup="SKIP",
            entry=None,
            stop_loss=None,
            target=None,
            risk_per_share=round(risk_per_share, 2),
            reward_per_share=round(reward_per_share, 2),
            rr_ratio=round(rr_ratio, 2) if rr_ratio is not None else None,
            position_size_shares=None,
            position_size_value=None,
            reason=f"R/R too low ({round(rr_ratio, 2) if rr_ratio else 'N/A'})",
        )

    return TradePlan(
        bias=bias,
        setup=setup,
        entry=round(adjusted_entry, 2),
        stop_loss=round(adjusted_stop, 2),
        target=round(adjusted_target, 2),
        risk_per_share=round(risk_per_share, 2),
        reward_per_share=round(reward_per_share, 2),
        rr_ratio=round(rr_ratio, 2),
        position_size_shares=shares,
        position_size_value=round(value, 2) if value is not None else None,
        reason=reason,
    )


def build_trade_plan(
    df: pd.DataFrame,
    structure: str,
    supports: list[float],
    resistances: list[float],
    portfolio_size_sek: float = 30000,
    risk_percent: float = 1.0,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
) -> TradePlan:
    if df.empty or len(df) < 5:
        return _empty_plan(setup="NONE", reason="Not enough data")

    work = df.copy()
    work["ema20"] = work["close"].ewm(span=20).mean()

    last = work.iloc[-1]
    prev = work.iloc[-2]
    price = float(last["close"])
    prev_close = float(prev["close"])
    ema20 = float(last["ema20"])

    ns = nearest_support(supports, price)
    nr = nearest_resistance(resistances, price)
    broken_resistances = [r for r in resistances if r < price]
    broken_supports = [s for s in supports if s > price]
    latest_broken_resistance = max(broken_resistances) if broken_resistances else None
    latest_broken_support = min(broken_supports) if broken_supports else None
    atr = float((df["high"] - df["low"]).rolling(14, min_periods=1).mean().iloc[-1])
    stop_buffer = max(atr * 0.8, price * 0.0003)

    # ---------- LONG SETUP ----------
    if structure in {"breakout", "uptrend", "bullish_bias", "range_near_highs", "extended_uptrend"}:
        if (
            latest_broken_resistance is not None
            and prev_close <= latest_broken_resistance
            and price > latest_broken_resistance
        ):
            entry = price
            stop = latest_broken_resistance - stop_buffer
            target = entry + 2 * (entry - stop)
            return _finalize_plan(
                bias="BULLISH",
                setup="BUY_BREAKOUT",
                entry=entry,
                stop_loss=stop,
                target=target,
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                fee_per_trade=fee_per_trade,
                slippage_points=slippage_points,
                reason="Fresh bullish breakout above resistance",
            )

        if price > ema20 and ns is not None:
            entry = max(ns, round(ema20, 2))
            stop = ns - stop_buffer
            target = entry + 2 * (entry - stop)
            if nr is not None and nr > entry:
                target = max(target, nr)

            return _finalize_plan(
                bias="BULLISH",
                setup="BUY_PULLBACK",
                entry=entry,
                stop_loss=stop,
                target=target,
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                fee_per_trade=fee_per_trade,
                slippage_points=slippage_points,
                reason="Bullish structure; prefer pullback toward support/EMA20",
            )

        return _empty_plan(
            reason="Bullish bias, but price is not near a planned pullback or fresh breakout trigger"
        )

    # ---------- SHORT SETUP ----------
    if structure in {"breakdown", "downtrend", "bearish_bias", "extended_downtrend"}:
        if (
            latest_broken_support is not None
            and prev_close >= latest_broken_support
            and price < latest_broken_support
        ):
            entry = price
            stop = latest_broken_support + stop_buffer
            target = entry - 2 * (stop - entry)
            return _finalize_plan(
                bias="BEARISH",
                setup="SELL_BREAKDOWN",
                entry=entry,
                stop_loss=stop,
                target=target,
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                fee_per_trade=fee_per_trade,
                slippage_points=slippage_points,
                reason="Fresh bearish breakdown below support",
            )

        if price < ema20 and nr is not None:
            entry = min(nr, round(ema20, 2))
            stop = nr + stop_buffer
            target = entry - 2 * (stop - entry)
            if ns is not None and ns < entry:
                target = min(target, ns)

            return _finalize_plan(
                bias="BEARISH",
                setup="SELL_RETEST",
                entry=entry,
                stop_loss=stop,
                target=target,
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                fee_per_trade=fee_per_trade,
                slippage_points=slippage_points,
                reason="Bearish structure; prefer short on retest into resistance/EMA20",
            )

    return _empty_plan()
