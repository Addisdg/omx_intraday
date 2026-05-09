from __future__ import annotations

import analysis.backtest as backtest_module
import pandas as pd

from analysis.backtest import (
    equity_curve,
    optimize_parameters,
    replay_strategy,
    split_train_test,
    summarize_backtest,
    summarize_by_setup,
    validate_out_of_sample,
)
from analysis.confidence import score_setup
from analysis.data_quality import assess_data_quality
from analysis.indicators import add_indicators
from analysis.levels import find_levels
from analysis.market_hours import format_timestamp, infer_market
from analysis.market_structure import classify_structure
from analysis.research import estimate_historical_edge, probability_from_edge, run_historical_research
from analysis.signals import classify_signal
from analysis.timeframes import compare_timeframes
from analysis.trade_engine import TradePlan, build_trade_plan, calculate_position_size
from analysis.volume import analyze_volume
from config.settings import load_settings, save_settings
from data.cache import load_cached_data, save_cached_data
from services.market_analysis import analyze_dataframe, research_dataframe
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


def test_backtest_replay_decision_pipeline_uses_history_only(monkeypatch) -> None:
    all_candles = _df(list(range(100, 110)))
    observed_decision_timestamps = []

    def fake_find_levels(history: pd.DataFrame, **kwargs) -> dict:
        assert history["timestamp"].max() < all_candles.iloc[len(history)]["timestamp"]
        return {"supports": [], "resistances": []}

    def fake_classify_structure(history: pd.DataFrame, **kwargs) -> str:
        assert history["timestamp"].max() < all_candles.iloc[len(history)]["timestamp"]
        return "range"

    def fake_build_trade_plan(df: pd.DataFrame, **kwargs) -> TradePlan:
        observed_decision_timestamps.append(df.iloc[-1]["timestamp"])
        assert df["timestamp"].max() < all_candles.iloc[len(df)]["timestamp"]
        return TradePlan("NEUTRAL", "WAIT", None, None, None, None, None, None, None, None, "test")

    monkeypatch.setattr(backtest_module, "find_levels", fake_find_levels)
    monkeypatch.setattr(backtest_module, "classify_structure", fake_classify_structure)
    monkeypatch.setattr(backtest_module, "build_trade_plan", fake_build_trade_plan)

    trades = replay_strategy(all_candles, warmup=3, max_hold_bars=2)

    assert trades.empty
    assert observed_decision_timestamps == [
        all_candles.iloc[idx]["timestamp"] for idx in range(3, len(all_candles) - 1)
    ]


def test_backtest_replay_records_anti_lookahead_audit_timestamps(monkeypatch) -> None:
    all_candles = _df(list(range(100, 110)))

    def fake_build_trade_plan(df: pd.DataFrame, **kwargs) -> TradePlan:
        entry = float(df.iloc[-1]["close"])
        return TradePlan(
            bias="BULLISH",
            setup="BUY_BREAKOUT",
            entry=entry,
            stop_loss=entry - 1,
            target=entry + 0.2,
            risk_per_share=1,
            reward_per_share=0.2,
            rr_ratio=0.2,
            position_size_shares=1,
            position_size_value=entry,
            reason="test plan",
        )

    monkeypatch.setattr(backtest_module, "find_levels", lambda *args, **kwargs: {"supports": [], "resistances": []})
    monkeypatch.setattr(backtest_module, "classify_structure", lambda *args, **kwargs: "breakout")
    monkeypatch.setattr(backtest_module, "build_trade_plan", fake_build_trade_plan)

    trades = replay_strategy(all_candles, warmup=3, max_hold_bars=2, prevent_overlaps=True)
    first_trade = trades.iloc[0]

    assert first_trade["decision_index"] == 3
    assert first_trade["timestamp"] == all_candles.iloc[3]["timestamp"]
    assert first_trade["history_start_timestamp"] == all_candles.iloc[0]["timestamp"]
    assert first_trade["history_end_timestamp"] == all_candles.iloc[3]["timestamp"]
    assert first_trade["first_resolution_timestamp"] == all_candles.iloc[4]["timestamp"]
    assert first_trade["first_resolution_timestamp"] > first_trade["history_end_timestamp"]


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
    assert "reward_risk" in confidence["factors"]
    assert confidence["factors"]["reward_risk"]["max_score"] == 22
    assert confidence["factors"]["reward_risk"]["reason"]


def test_confidence_score_explains_cap_when_no_actionable_setup() -> None:
    df = _df([100, 101, 102, 103, 104, 105])
    plan = TradePlan(
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
    volume = {"volume_state": "spike", "reason": "Volume spike", "relative_volume": 3.0}

    confidence = score_setup(
        df=df,
        structure="uptrend",
        signal={"signal": "WAIT FOR PULLBACK"},
        trade_plan=plan,
        supports=[104.9],
        resistances=[106.0],
        volume_read=volume,
    )

    assert confidence["score"] <= 55
    assert confidence["cap_applied"] is True
    assert confidence["raw_score"] > confidence["score"]
    assert "No actionable setup is active; confidence is capped." in confidence["notes"]


def test_timeframe_comparison_reports_aligned_and_conflicting_context() -> None:
    aligned = compare_timeframes("uptrend", "breakout", higher_interval="60m")
    conflicting = compare_timeframes("uptrend", "downtrend", higher_interval="60m")
    mixed = compare_timeframes("uptrend", "range", higher_interval="60m")

    assert aligned["status"] == "aligned"
    assert aligned["score_adjustment"] > 0
    assert conflicting["status"] == "conflicting"
    assert conflicting["score_adjustment"] < 0
    assert mixed["status"] == "mixed"
    assert mixed["score_adjustment"] == 0


def test_confidence_score_includes_timeframe_confirmation_factor() -> None:
    df = _df([100, 101, 102, 103, 104, 106])
    levels = {"supports": [101.0, 103.0], "resistances": [105.0]}
    structure = "breakout"
    signal = classify_signal(df, levels["supports"], levels["resistances"], structure)
    plan = build_trade_plan(df, structure, levels["supports"], levels["resistances"])
    volume = analyze_volume(df)
    confirmation = compare_timeframes("breakout", "downtrend", higher_interval="60m")

    confidence = score_setup(
        df,
        structure,
        signal,
        plan,
        levels["supports"],
        levels["resistances"],
        volume,
        timeframe_confirmation=confirmation,
    )

    assert confidence["components"]["timeframe_confirmation"] == -8
    assert confidence["factors"]["timeframe_confirmation"]["reason"] == confirmation["reason"]


def test_data_quality_passes_clean_candles() -> None:
    quality = assess_data_quality(_df([100, 101, 102, 103, 104]))

    assert quality["status"] == "ok"
    assert quality["row_count"] == 5
    assert quality["issues"] == []


def test_data_quality_warns_on_duplicate_timestamp_and_bad_ohlc() -> None:
    df = _df([100, 101, 102, 103, 104])
    df.loc[2, "timestamp"] = df.loc[1, "timestamp"]
    df.loc[3, "high"] = df.loc[3, "low"] - 1
    df["volume"] = 0

    quality = assess_data_quality(df)

    assert quality["status"] == "warning"
    assert any("duplicate timestamp" in issue for issue in quality["issues"])
    assert any("inconsistent OHLC" in issue for issue in quality["issues"])
    assert any("Volume is mostly zero" in issue for issue in quality["issues"])


def test_data_quality_marks_missing_required_columns_invalid() -> None:
    quality = assess_data_quality(_df([100, 101, 102]).drop(columns=["close"]))

    assert quality["status"] == "invalid"
    assert any("Missing required columns" in issue for issue in quality["issues"])


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


def test_train_test_split_preserves_chronological_order() -> None:
    df = _df(list(range(100, 110)))

    train, test = split_train_test(df, train_fraction=0.6)

    assert len(train) == 6
    assert len(test) == 4
    assert train.iloc[-1]["timestamp"] < test.iloc[0]["timestamp"]


def test_out_of_sample_validation_returns_split_summaries(monkeypatch) -> None:
    df = _df(list(range(100, 120)))

    def fake_replay_strategy(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp": df.iloc[-2]["timestamp"],
                    "setup": "BUY_BREAKOUT",
                    "outcome": "target",
                    "r_multiple": 1.5,
                    "rr_ratio": 2.0,
                }
            ]
        )

    monkeypatch.setattr(backtest_module, "replay_strategy", fake_replay_strategy)

    validation = validate_out_of_sample(df, train_fraction=0.5, warmup=3, max_hold_bars=2)

    assert validation["split_index"] == 10
    assert validation["split_timestamp"] == df.iloc[10]["timestamp"]
    assert validation["in_sample_summary"].trades == 1
    assert validation["out_of_sample_summary"].trades == 1
    assert validation["verdict"] == "Out-of-sample validation supports the in-sample result"


def test_research_edge_and_probability() -> None:
    trades = pd.DataFrame(
        [
            {"setup": "BUY_BREAKOUT", "outcome": "target", "r_multiple": 2.0},
            {"setup": "BUY_BREAKOUT", "outcome": "stop", "r_multiple": -1.0},
            {"setup": "BUY_BREAKOUT", "outcome": "target", "r_multiple": 2.0},
            {"setup": "BUY_BREAKOUT", "outcome": "timeout", "r_multiple": 0.5},
            {"setup": "BUY_BREAKOUT", "outcome": "target", "r_multiple": 2.0},
        ]
    )

    edge = estimate_historical_edge(trades, "BUY_BREAKOUT")
    probability = probability_from_edge(edge, fallback_confidence=50)

    assert edge.sample_size == 5
    assert edge.win_rate == 0.8
    assert probability > 50


def test_service_analyze_dataframe_returns_current_read() -> None:
    result = analyze_dataframe(_df([100, 101, 102, 103, 104, 106]))

    assert result["status"] == "ok"
    assert "confidence" in result
    assert result["data_quality"]["status"] == "ok"
    assert "trade_plan" in result


def test_service_analyze_dataframe_returns_timeframe_confirmation() -> None:
    lower = _df([100, 101, 102, 103, 104, 106])
    higher = _df(list(range(100, 130)))

    result = analyze_dataframe(lower, confirmation_df=higher, confirmation_interval="60m")

    assert result["status"] == "ok"
    assert result["timeframe_confirmation"] is not None
    assert "timeframe_confirmation" in result["confidence"]["components"]


def test_service_research_dataframe_returns_research_bundle() -> None:
    df = _df(list(range(100, 145)))

    result = research_dataframe(df, warmup=20, max_hold_bars=5)

    assert result["status"] == "ok"
    assert "current" in result
    assert "research" in result
    assert "validation" in result["research"]


def test_run_historical_research_returns_decision() -> None:
    df = _df(list(range(100, 145)))

    result = run_historical_research(df, current_setup="BUY_BREAKOUT", confidence_score=60, warmup=20)

    assert "probability" in result
    assert "decision" in result
