from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from data.provider_yfinance import YFinanceProvider
from services.market_analysis import analyze_symbol, research_dataframe


app = FastAPI(title="OMX Intraday Analysis API")


class AnalyzeRequest(BaseModel):
    symbol: str
    interval: str = "1m"
    period: str | None = None
    portfolio_size_sek: float = 30_000
    risk_percent: float = 1.0
    fee_per_trade: float = 0.0
    slippage_points: float = 0.0


class ResearchRequest(AnalyzeRequest):
    warmup: int = 30
    max_hold_bars: int = 30
    train_fraction: float | None = 0.7


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
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return _json_safe(value.__dict__)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
