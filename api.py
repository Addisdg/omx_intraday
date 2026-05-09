from __future__ import annotations

from dataclasses import asdict, is_dataclass
import math
from typing import Literal

from fastapi import FastAPI
import pandas as pd
from pydantic import BaseModel, Field

from data.provider_yfinance import YFinanceProvider
from services.market_analysis import analyze_symbol, research_dataframe


app = FastAPI(title="OMX Intraday Analysis API")

Interval = Literal["1m", "2m", "5m", "15m", "30m", "60m", "1d"]
Period = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"]
ConfirmationInterval = Literal["15m", "30m", "60m", "1d"]


class AnalyzeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    interval: Interval = "1m"
    period: Period | None = None
    confirmation_interval: ConfirmationInterval | None = None
    portfolio_size_sek: float = Field(default=30_000, ge=1_000, le=10_000_000)
    risk_percent: float = Field(default=1.0, ge=0.1, le=10.0)
    fee_per_trade: float = Field(default=0.0, ge=0.0, le=10_000.0)
    slippage_points: float = Field(default=0.0, ge=0.0, le=100.0)


class ResearchRequest(AnalyzeRequest):
    warmup: int = Field(default=30, ge=10, le=240)
    max_hold_bars: int = Field(default=30, ge=1, le=500)
    train_fraction: float | None = Field(default=0.7, gt=0.0, lt=1.0)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    result = analyze_symbol(
        symbol=request.symbol,
        interval=request.interval,
        period=request.period,
        portfolio_size_sek=request.portfolio_size_sek,
        risk_percent=request.risk_percent,
        fee_per_trade=request.fee_per_trade,
        slippage_points=request.slippage_points,
        confirmation_interval=request.confirmation_interval,
    )
    return _json_safe(result)


@app.post("/research")
def research(request: ResearchRequest) -> dict:
    provider = YFinanceProvider()
    df = provider.get_history(
        symbol=request.symbol,
        interval=request.interval,
        period=request.period or "1mo",
        save_to_cache=True,
    )
    result = research_dataframe(
        df,
        portfolio_size_sek=request.portfolio_size_sek,
        risk_percent=request.risk_percent,
        warmup=request.warmup,
        max_hold_bars=request.max_hold_bars,
        train_fraction=request.train_fraction,
        fee_per_trade=request.fee_per_trade,
        slippage_points=request.slippage_points,
    )

    if result.get("status") == "ok":
        research_result = result["research"]
        research_result["trades"] = research_result["trades"].to_dict(orient="records")
        research_result["by_setup"] = research_result["by_setup"].to_dict(orient="records")
    return _json_safe(result)


def _json_safe(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, pd.DataFrame):
        return _json_safe(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        return _json_safe(value.to_dict())
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
