from __future__ import annotations

import pandas as pd

from analysis.confidence import score_setup
from analysis.data_quality import assess_data_quality
from analysis.indicators import summarize_indicator_context
from analysis.levels import find_levels
from analysis.market_structure import analyze_market_regime
from analysis.research import build_similarity_context, run_historical_research
from analysis.signals import classify_signal
from analysis.timeframes import build_timeframe_confirmation
from analysis.trade_engine import build_trade_plan
from analysis.volatility import analyze_volatility_regime
from analysis.volume import analyze_volume
from data.provider_base import provider_metadata_from_df
from data.provider_yfinance import YFinanceProvider
from ui.labels import setup_label, signal_label


def analyze_dataframe(
    df: pd.DataFrame,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
    confirmation_df: pd.DataFrame | None = None,
    confirmation_interval: str | None = None,
) -> dict:
    provider_metadata = provider_metadata_from_df(df)
    data_quality = assess_data_quality(df)
    if df is None or df.empty:
        return {"status": "no_data", "data_quality": data_quality, "provider_metadata": provider_metadata}
    if data_quality["status"] == "invalid":
        return {"status": "invalid_data", "data_quality": data_quality, "provider_metadata": provider_metadata}

    levels = find_levels(df, window=3, tolerance=None, min_touches=2)
    market_regime = analyze_market_regime(df, lookback=min(30, len(df)))
    structure = market_regime["structure"]
    signal = classify_signal(df, levels["supports"], levels["resistances"], structure)
    volume = analyze_volume(df)
    volatility = analyze_volatility_regime(df)
    indicator_context = summarize_indicator_context(df)
    plan = build_trade_plan(
        df=df,
        structure=structure,
        supports=levels["supports"],
        resistances=levels["resistances"],
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
    )
    timeframe_confirmation = None
    if confirmation_df is not None or confirmation_interval is not None:
        timeframe_confirmation = build_timeframe_confirmation(
            lower_structure=structure,
            higher_df=confirmation_df,
            higher_interval=confirmation_interval,
        )
    confidence = score_setup(
        df,
        structure,
        signal,
        plan,
        levels["supports"],
        levels["resistances"],
        volume,
        timeframe_confirmation=timeframe_confirmation,
        volatility_regime=volatility,
        indicator_context=indicator_context,
    )

    return {
        "status": "ok",
        "data_quality": data_quality,
        "provider_metadata": provider_metadata,
        "last_close": float(df.iloc[-1]["close"]),
        "last_timestamp": str(df.iloc[-1]["timestamp"]),
        "levels": levels,
        "structure": structure,
        "market_regime": market_regime,
        "signal": signal,
        "signal_label": signal_label(signal["signal"]),
        "volume": volume,
        "volatility": volatility,
        "indicators": indicator_context,
        "timeframe_confirmation": timeframe_confirmation,
        "trade_plan": plan,
        "setup_label": setup_label(plan.setup),
        "confidence": confidence,
    }


def analyze_symbol(
    symbol: str,
    interval: str = "1m",
    period: str | None = None,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
    confirmation_interval: str | None = None,
) -> dict:
    provider = YFinanceProvider()
    df = provider.get_intraday(symbol, interval, period=period, save_to_cache=True)
    confirmation_df = None
    if confirmation_interval:
        confirmation_df = provider.get_history(
            symbol=symbol,
            interval=confirmation_interval,
            period=_confirmation_period(confirmation_interval),
            save_to_cache=True,
        )
    result = analyze_dataframe(
        df,
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
        confirmation_df=confirmation_df,
        confirmation_interval=confirmation_interval,
    )
    result["symbol"] = symbol
    result["interval"] = interval
    result["period"] = period
    result["confirmation_interval"] = confirmation_interval
    return result


def _confirmation_period(interval: str) -> str:
    if interval == "1d":
        return "1y"
    if interval in {"30m", "60m"}:
        return "1mo"
    return "5d"


def research_dataframe(
    df: pd.DataFrame,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    warmup: int = 30,
    max_hold_bars: int = 30,
    train_fraction: float | None = 0.7,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
) -> dict:
    current = analyze_dataframe(
        df,
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
    )
    if current["status"] != "ok":
        return {"status": current["status"], "data_quality": current.get("data_quality")}

    research = run_historical_research(
        df=df,
        current_setup=current["trade_plan"].setup,
        confidence_score=current["confidence"]["score"],
        current_context=build_similarity_context(
            setup=current["trade_plan"].setup,
            structure=current["structure"],
            confidence_score=current["confidence"]["score"],
            volume_state=current["volume"]["volume_state"],
            rr_ratio=current["trade_plan"].rr_ratio,
            market_regime=current["market_regime"],
        ),
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        warmup=warmup,
        max_hold_bars=max_hold_bars,
        train_fraction=train_fraction,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
    )
    return {"status": "ok", "current": current, "research": research}
