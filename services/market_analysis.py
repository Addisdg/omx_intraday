from __future__ import annotations

import pandas as pd

from analysis.confidence import score_setup
from analysis.data_quality import assess_data_quality
from analysis.levels import find_levels
from analysis.market_structure import classify_structure
from analysis.research import run_historical_research
from analysis.signals import classify_signal
from analysis.trade_engine import build_trade_plan
from analysis.volume import analyze_volume
from data.provider_yfinance import YFinanceProvider
from ui.labels import setup_label, signal_label


def analyze_dataframe(
    df: pd.DataFrame,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
) -> dict:
    data_quality = assess_data_quality(df)
    if df is None or df.empty:
        return {"status": "no_data", "data_quality": data_quality}
    if data_quality["status"] == "invalid":
        return {"status": "invalid_data", "data_quality": data_quality}

    levels = find_levels(df, window=3, tolerance=None, min_touches=2)
    structure = classify_structure(df, lookback=min(30, len(df)))
    signal = classify_signal(df, levels["supports"], levels["resistances"], structure)
    volume = analyze_volume(df)
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
    confidence = score_setup(
        df,
        structure,
        signal,
        plan,
        levels["supports"],
        levels["resistances"],
        volume,
    )

    return {
        "status": "ok",
        "data_quality": data_quality,
        "last_close": float(df.iloc[-1]["close"]),
        "last_timestamp": str(df.iloc[-1]["timestamp"]),
        "levels": levels,
        "structure": structure,
        "signal": signal,
        "signal_label": signal_label(signal["signal"]),
        "volume": volume,
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
) -> dict:
    provider = YFinanceProvider()
    df = provider.get_intraday(symbol, interval, period=period, save_to_cache=True)
    result = analyze_dataframe(
        df,
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
    )
    result["symbol"] = symbol
    result["interval"] = interval
    result["period"] = period
    return result


def research_dataframe(
    df: pd.DataFrame,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    warmup: int = 30,
    max_hold_bars: int = 30,
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
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        warmup=warmup,
        max_hold_bars=max_hold_bars,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
    )
    return {"status": "ok", "current": current, "research": research}
