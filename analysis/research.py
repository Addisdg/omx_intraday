from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from analysis.backtest import (
    BacktestSummary,
    replay_strategy,
    summarize_backtest,
    summarize_by_setup,
)


@dataclass(frozen=True)
class HistoricalEdge:
    setup: str
    sample_size: int
    win_rate: float | None
    average_r: float | None
    total_r: float | None
    verdict: str


def estimate_historical_edge(
    trades: pd.DataFrame,
    setup: str,
    min_sample: int = 5,
) -> HistoricalEdge:
    if trades.empty or setup in {"WAIT", "SKIP", "NONE"}:
        return HistoricalEdge(setup, 0, None, None, None, "No active setup to compare")

    similar = trades[trades["setup"] == setup]
    if similar.empty:
        return HistoricalEdge(setup, 0, None, None, None, "No matching historical setups")

    closed = similar[similar["outcome"].isin(["target", "stop", "timeout"])]
    sample_size = len(closed)
    if sample_size == 0:
        return HistoricalEdge(setup, 0, None, None, None, "No closed historical setups")

    wins = int((closed["r_multiple"] > 0).sum())
    win_rate = wins / sample_size
    average_r = float(closed["r_multiple"].mean())
    total_r = float(closed["r_multiple"].sum())

    if sample_size < min_sample:
        verdict = "Low confidence: too few similar historical setups"
    elif average_r > 0.25 and win_rate >= 0.5:
        verdict = "Historically favorable setup"
    elif average_r > 0:
        verdict = "Slight historical edge"
    else:
        verdict = "No positive historical edge detected"

    return HistoricalEdge(
        setup=setup,
        sample_size=sample_size,
        win_rate=win_rate,
        average_r=average_r,
        total_r=total_r,
        verdict=verdict,
    )


def probability_from_edge(edge: HistoricalEdge, fallback_confidence: int) -> int:
    if edge.win_rate is None:
        return max(5, min(95, fallback_confidence))

    sample_weight = min(edge.sample_size / 30, 1.0)
    historical_probability = edge.win_rate * 100
    blended = historical_probability * sample_weight + fallback_confidence * (1 - sample_weight)
    return max(5, min(95, int(round(blended))))


def run_historical_research(
    df: pd.DataFrame,
    current_setup: str,
    confidence_score: int,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    warmup: int = 30,
    max_hold_bars: int = 30,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
) -> dict:
    trades = replay_strategy(
        df=df,
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        warmup=warmup,
        max_hold_bars=max_hold_bars,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
        prevent_overlaps=True,
    )
    summary = summarize_backtest(trades)
    by_setup = summarize_by_setup(trades)
    edge = estimate_historical_edge(trades, current_setup)
    probability = probability_from_edge(edge, confidence_score)

    return {
        "trades": trades,
        "summary": summary,
        "by_setup": by_setup,
        "edge": edge,
        "probability": probability,
        "decision": decision_label(probability, edge, summary),
    }


def decision_label(
    probability: int,
    edge: HistoricalEdge,
    summary: BacktestSummary,
) -> str:
    if edge.sample_size < 5:
        return "Research only: not enough similar history"
    if probability >= 65 and summary.total_r > 0:
        return "Watchlist candidate: historical edge is positive"
    if probability <= 40 or (edge.average_r is not None and edge.average_r <= 0):
        return "Avoid or wait: historical edge is weak"
    return "Neutral: wait for stronger confirmation"
