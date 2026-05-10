from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from analysis.backtest import (
    BacktestSummary,
    confidence_bucket,
    replay_strategy,
    rr_bucket,
    summarize_backtest,
    summarize_by_setup,
    validate_out_of_sample,
)
from analysis.timeframes import bias_from_structure


@dataclass(frozen=True)
class HistoricalEdge:
    setup: str
    sample_size: int
    win_rate: float | None
    average_r: float | None
    total_r: float | None
    verdict: str
    matched_dimensions: tuple[str, ...] = ()
    match_description: str = "setup only"


SIMILARITY_DIMENSIONS = (
    "structure",
    "trend_bias",
    "volume_state",
    "rr_bucket",
    "confidence_bucket",
    "regime_trend_state",
    "regime_range_state",
    "regime_breakout_state",
)


def estimate_historical_edge(
    trades: pd.DataFrame,
    setup: str,
    context: dict | None = None,
    min_sample: int = 5,
) -> HistoricalEdge:
    if trades.empty or setup in {"WAIT", "SKIP", "NONE"}:
        return HistoricalEdge(setup, 0, None, None, None, "No active setup to compare")

    similar, matched_dimensions = _select_similar_trades(trades, setup, context, min_sample)
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
        matched_dimensions=matched_dimensions,
        match_description=_match_description(matched_dimensions),
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
    current_context: dict | None = None,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    warmup: int = 30,
    max_hold_bars: int = 30,
    train_fraction: float | None = 0.7,
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
    context = current_context or build_similarity_context(
        setup=current_setup,
        confidence_score=confidence_score,
    )
    edge = estimate_historical_edge(trades, current_setup, context=context)
    probability = probability_from_edge(edge, confidence_score)
    validation = (
        validate_out_of_sample(
            df=df,
            portfolio_size_sek=portfolio_size_sek,
            risk_percent=risk_percent,
            warmup=warmup,
            max_hold_bars=max_hold_bars,
            train_fraction=train_fraction,
            fee_per_trade=fee_per_trade,
            slippage_points=slippage_points,
            prevent_overlaps=True,
        )
        if train_fraction is not None
        else None
    )
    quality = assess_research_quality(
        edge=edge,
        summary=summary,
        context=context,
        validation=validation,
    )

    return {
        "trades": trades,
        "summary": summary,
        "by_setup": by_setup,
        "edge": edge,
        "similarity_context": context,
        "quality": quality,
        "probability": probability,
        "validation": validation,
        "decision": decision_label(probability, edge, summary, validation),
    }


def assess_research_quality(
    edge: HistoricalEdge,
    summary: BacktestSummary,
    context: dict | None = None,
    validation: dict | None = None,
    min_sample: int = 5,
) -> dict:
    requested_dimensions = tuple(
        dimension for dimension in SIMILARITY_DIMENSIONS if context and context.get(dimension) is not None
    )
    matched_count = len(edge.matched_dimensions)
    requested_count = len(requested_dimensions)
    fallback_level = _fallback_level(matched_count, requested_count)
    validation_status = _validation_status(validation)
    warnings = _quality_warnings(edge, summary, fallback_level, validation_status, min_sample)
    quality = _quality_grade(edge, fallback_level, validation_status, min_sample)

    return {
        "quality": quality,
        "sample_size": edge.sample_size,
        "minimum_sample": min_sample,
        "total_replayed_trades": summary.trades,
        "matched_dimensions": edge.matched_dimensions,
        "requested_dimensions": requested_dimensions,
        "match_description": edge.match_description,
        "fallback_level": fallback_level,
        "validation_status": validation_status,
        "warnings": warnings,
        "reason": _quality_reason(quality, edge.sample_size, fallback_level, validation_status),
    }


def decision_label(
    probability: int,
    edge: HistoricalEdge,
    summary: BacktestSummary,
    validation: dict | None = None,
) -> str:
    if edge.sample_size < 5:
        return "Research only: not enough similar history"
    if validation is not None:
        out_summary = validation["out_of_sample_summary"]
        if summary.total_r > 0 and out_summary.trades > 0 and out_summary.total_r <= 0:
            return "Research only: edge did not hold out of sample"
    if probability >= 65 and summary.total_r > 0:
        return "Watchlist candidate: historical edge is positive"
    if probability <= 40 or (edge.average_r is not None and edge.average_r <= 0):
        return "Avoid or wait: historical edge is weak"
    return "Neutral: wait for stronger confirmation"


def _fallback_level(matched_count: int, requested_count: int) -> str:
    if requested_count == 0 or matched_count == 0:
        return "setup_only"
    if matched_count == requested_count:
        return "full_context"
    return "partial_context"


def _validation_status(validation: dict | None) -> str:
    if validation is None:
        return "not_run"
    verdict = validation.get("verdict", "")
    out_summary = validation.get("out_of_sample_summary")
    if out_summary is not None and getattr(out_summary, "trades", 0) == 0:
        return "no_out_of_sample_trades"
    if "supports" in verdict.lower():
        return "supported"
    if "did not hold" in verdict.lower():
        return "failed"
    if "not enough" in verdict.lower():
        return "insufficient_data"
    return "mixed"


def _quality_warnings(
    edge: HistoricalEdge,
    summary: BacktestSummary,
    fallback_level: str,
    validation_status: str,
    min_sample: int,
) -> list[str]:
    warnings = []
    if summary.trades == 0:
        warnings.append("No replayed trades were generated for this run.")
    if edge.sample_size < min_sample:
        warnings.append("Similar setup sample is below the minimum reliability threshold.")
    if fallback_level == "setup_only":
        warnings.append("Similarity fell back to setup-only matching.")
    elif fallback_level == "partial_context":
        warnings.append("Similarity used partial context because stricter matching had too few samples.")
    if validation_status in {"failed", "no_out_of_sample_trades", "insufficient_data"}:
        warnings.append("Out-of-sample validation does not strongly support the historical read.")
    if validation_status == "not_run":
        warnings.append("Out-of-sample validation was not run.")
    return warnings


def _quality_grade(
    edge: HistoricalEdge,
    fallback_level: str,
    validation_status: str,
    min_sample: int,
) -> str:
    if edge.sample_size == 0:
        return "No evidence"
    if edge.sample_size < min_sample:
        return "Low"
    if validation_status in {"failed", "no_out_of_sample_trades", "insufficient_data"}:
        return "Low"
    if fallback_level == "full_context" and edge.sample_size >= min_sample * 2 and validation_status == "supported":
        return "High"
    if fallback_level in {"full_context", "partial_context"}:
        return "Moderate"
    return "Low"


def _quality_reason(
    quality: str,
    sample_size: int,
    fallback_level: str,
    validation_status: str,
) -> str:
    return (
        f"Research quality is {quality.lower()} with {sample_size} similar samples, "
        f"{fallback_level.replace('_', ' ')} matching, and validation status {validation_status.replace('_', ' ')}."
    )


def build_similarity_context(
    setup: str,
    structure: str | None = None,
    confidence_score: int | float | None = None,
    volume_state: str | None = None,
    rr_ratio: float | None = None,
    market_regime: dict | None = None,
) -> dict:
    context = {"setup": setup}
    if structure is not None:
        context["structure"] = structure
        context["trend_bias"] = bias_from_structure(structure)
    if volume_state is not None:
        context["volume_state"] = volume_state
    if rr_ratio is not None:
        context["rr_bucket"] = rr_bucket(rr_ratio)
    if confidence_score is not None:
        context["confidence_bucket"] = confidence_bucket(confidence_score)
    if market_regime is not None:
        _add_regime_context(context, market_regime)
    return context


def _add_regime_context(context: dict, market_regime: dict) -> None:
    regime_fields = {
        "regime_trend_state": "trend_state",
        "regime_range_state": "range_state",
        "regime_breakout_state": "breakout_state",
    }
    for context_key, regime_key in regime_fields.items():
        value = market_regime.get(regime_key)
        if value is not None and value != "unknown":
            context[context_key] = value


def _select_similar_trades(
    trades: pd.DataFrame,
    setup: str,
    context: dict | None,
    min_sample: int,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    setup_matches = trades[trades["setup"] == setup]
    if setup_matches.empty or not context:
        return setup_matches, ()

    available_dimensions = tuple(
        dimension
        for dimension in SIMILARITY_DIMENSIONS
        if dimension in setup_matches.columns and context.get(dimension) is not None
    )
    for keep_count in range(len(available_dimensions), 0, -1):
        dimensions = available_dimensions[:keep_count]
        candidate = setup_matches.copy()
        for dimension in dimensions:
            candidate = candidate[candidate[dimension] == context[dimension]]
        closed_count = int(candidate["outcome"].isin(["target", "stop", "timeout"]).sum()) if "outcome" in candidate else 0
        if closed_count >= min_sample:
            return candidate, dimensions

    return setup_matches, ()


def _match_description(dimensions: tuple[str, ...]) -> str:
    if not dimensions:
        return "setup only"
    return "setup + " + " + ".join(dimension.replace("_", " ") for dimension in dimensions)
