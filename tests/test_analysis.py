from __future__ import annotations

import pandas as pd

from analysis.backtest import (
    equity_curve,
    optimize_parameters,
    replay_strategy,
    summarize_backtest,
    summarize_by_setup,
)
from analysis.confidence import score_setup
from analysis.indicators import add_indicators
from analysis.levels import find_levels
from analysis.market_hours import format_timestamp, infer_market
from analysis.market_structure import classify_structure
from analysis.signals import classify_signal
from analysis.trade_engine import build_trade_plan, calculate_position_size
from analysis.volume import analyze_volume
from config.settings import load_settings, save_settings
from data.cache import load_cached_data, save_cached_data
from ui.labels import setup_label


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


def test_indicators_add_ema_vwap_and_atr_bands() -> None:
    df = _df([100, 101, 102, 103, 104])

    enriched = add_indicators(df, ema_spans=[9, 20], include_vwap=True, include_atr_bands=True)

    assert {"ema9", "ema20", "vwap", "atr", "atr_upper", "atr_lower"}.issubset(enriched.columns)
    assert enriched["ema20"].notna().all()


def test_cache_round_trip(tmp_path) -> None:
    df = _df([100, 101, 102])

    save_cached_data(df, "^OMX", "1m", cache_dir=tmp_path)
    loaded = load_cached_data("^OMX", "1m", cache_dir=tmp_path)

    assert len(loaded) == len(df)
    assert list(loaded.columns) == list(df.columns)


def test_market_helpers_infer_and_format_timezone() -> None:
    assert infer_market("^OMX") == "OMX"
    assert infer_market("BTC-USD") == "CRYPTO"
    assert infer_market("EURUSD=X") == "FX"

    formatted = format_timestamp(pd.Timestamp("2026-04-24 10:00", tz="UTC"), "Europe/Stockholm")

    assert "2026-04-24" in formatted
    assert "CEST" in formatted


def test_backtest_replay_returns_summary() -> None:
    df = _df(
        [
            100,
            101,
            102,
            103,
            104,
            105,
            106,
            105,
            104,
            103,
            102,
            101,
            100,
            99,
            98,
            97,
            96,
            95,
            94,
            93,
            92,
            91,
            90,
            89,
            88,
            87,
            86,
            85,
            84,
            83,
            82,
            81,
            80,
            79,
            78,
        ]
    )

    trades = replay_strategy(df, warmup=20, max_hold_bars=5)
    summary = summarize_backtest(trades)

    assert summary.trades == len(trades)


def test_volume_analysis_detects_spike() -> None:
    df = _df([100, 101, 102, 103, 104])
    df.loc[df.index[-1], "volume"] = 5_000

    volume = analyze_volume(df, lookback=5)

    assert volume["volume_state"] == "spike"
    assert volume["relative_volume"] is not None


def test_confidence_score_returns_components() -> None:
    df = _df([100, 101, 102, 103, 104, 106])
    levels = {"supports": [101.0, 103.0], "resistances": [105.0]}
    structure = "breakout"
    signal = classify_signal(df, levels["supports"], levels["resistances"], structure)
    plan = build_trade_plan(df, structure, levels["supports"], levels["resistances"])
    volume = analyze_volume(df)

    confidence = score_setup(df, structure, signal, plan, levels["supports"], levels["resistances"], volume)

    assert 0 <= confidence["score"] <= 100
    assert "reward_risk" in confidence["components"]


def test_setup_label_is_safer_language() -> None:
    assert setup_label("SELL_BREAKDOWN") == "Potential bearish breakdown scenario"


def test_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.json"

    save_settings({"symbol": "AAPL", "risk_percent": 2.0}, path=path)
    loaded = load_settings(path=path)

    assert loaded["symbol"] == "AAPL"
    assert loaded["risk_percent"] == 2.0
    assert "interval" in loaded


def test_backtest_extra_summaries_and_optimization() -> None:
    df = _df(list(range(100, 140)))

    trades = replay_strategy(df, warmup=20, max_hold_bars=5, prevent_overlaps=True)
    curve = equity_curve(trades)
    by_setup = summarize_by_setup(trades)
    scan = optimize_parameters(
        df,
        portfolio_size_sek=30_000,
        risk_percent=1.0,
        warmup_values=[20],
        max_hold_values=[5, 10],
    )

    assert len(curve) == len(trades)
    assert "setup" in by_setup.columns
    assert len(scan) == 2
