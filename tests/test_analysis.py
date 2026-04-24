from __future__ import annotations

import pandas as pd

from analysis.levels import find_levels
from analysis.market_structure import classify_structure
from analysis.signals import classify_signal
from analysis.trade_engine import build_trade_plan, calculate_position_size


def _df(closes: list[float]) -> pd.DataFrame:
    rows = []
    for idx, close in enumerate(closes):
        rows.append(
            {
                "timestamp": pd.Timestamp("2026-04-24 09:00") + pd.Timedelta(minutes=idx),
                "open": close - 0.1,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 1_000,
            }
        )
    return pd.DataFrame(rows)


def test_trade_plan_waits_without_crashing_when_bullish_but_no_support() -> None:
    df = _df([100, 101, 102, 103, 102.5, 102.2])

    plan = build_trade_plan(
        df=df,
        structure="bullish_bias",
        supports=[],
        resistances=[],
    )

    assert plan.bias == "NEUTRAL"
    assert plan.setup == "WAIT"


def test_trade_plan_creates_fresh_breakout_plan() -> None:
    df = _df([100, 101, 102, 103, 104, 106])

    plan = build_trade_plan(
        df=df,
        structure="breakout",
        supports=[101.0, 103.0],
        resistances=[105.0],
        portfolio_size_sek=30_000,
        risk_percent=1.0,
    )

    assert plan.bias == "BULLISH"
    assert plan.setup == "BUY_BREAKOUT"
    assert plan.entry == 106.0
    assert plan.stop_loss is not None
    assert plan.stop_loss < plan.entry
    assert plan.rr_ratio is not None
    assert plan.rr_ratio >= 2


def test_trade_plan_creates_fresh_breakdown_plan() -> None:
    df = _df([106, 105, 104, 103, 102, 100])

    plan = build_trade_plan(
        df=df,
        structure="breakdown",
        supports=[101.0],
        resistances=[103.0, 105.0],
        portfolio_size_sek=30_000,
        risk_percent=1.0,
    )

    assert plan.bias == "BEARISH"
    assert plan.setup == "SELL_BREAKDOWN"
    assert plan.entry == 100.0
    assert plan.stop_loss is not None
    assert plan.stop_loss > plan.entry
    assert plan.rr_ratio is not None
    assert plan.rr_ratio >= 2


def test_position_size_is_capped_by_buying_power() -> None:
    shares, value, risk = calculate_position_size(
        portfolio_size_sek=1_000,
        risk_percent=10,
        entry=250,
        stop_loss=249,
    )

    assert shares == 4
    assert value == 1_000
    assert risk == 1


def test_adaptive_levels_return_supports_and_resistances() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-04-24 09:00", periods=11, freq="min"),
            "open": [100, 101, 102, 101, 100, 101, 102, 101, 100, 101, 102],
            "high": [101, 103, 105, 103, 101, 103, 105.1, 103, 101, 103, 104],
            "low": [99, 98, 100, 98.1, 99, 98, 100, 98.2, 99, 98, 100],
            "close": [100, 102, 104, 102, 100, 102, 104, 102, 100, 102, 103],
            "volume": [1_000] * 11,
        }
    )

    levels = find_levels(df, window=1, tolerance=None, min_touches=2)

    assert levels["supports"]
    assert levels["resistances"]


def test_signal_reports_bullish_bias_above_detected_range() -> None:
    df = _df([100, 101, 102, 103, 104, 106])

    signal = classify_signal(
        df=df,
        supports=[101.0, 103.0],
        resistances=[104.0, 105.0],
        structure="breakout",
    )

    assert signal["signal"] == "BULLISH BIAS"
    assert signal["nearest_resistance"] is None


def test_structure_detects_uptrend() -> None:
    df = _df(list(range(100, 125)))

    assert classify_structure(df, lookback=25) in {"breakout", "extended_uptrend", "uptrend"}
