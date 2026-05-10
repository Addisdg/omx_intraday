from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.screener import calculate_rank_components, candidate_filter_result
from data.provider_yfinance import YFinanceProvider
from services.market_analysis import research_dataframe


st.set_page_config(page_title="Stock Screener", layout="wide")
st.title("Historical Edge Screener")
st.caption("Rank many symbols by current setup quality plus historical replay edge.")

symbols_text = st.sidebar.text_area(
    "Symbols",
    value="AAPL\nMSFT\nNVDA\nSPY\nBTC-USD\nEURUSD=X",
    height=180,
)
interval = st.sidebar.selectbox("Interval", ["5m", "15m", "30m", "60m", "1d"], index=1)
period = st.sidebar.selectbox("Period", ["5d", "1mo", "3mo", "6mo", "1y", "2y"], index=1)
portfolio_size = st.sidebar.number_input("Portfolio size", 1_000, 10_000_000, 30_000, 1_000)
risk_percent = st.sidebar.number_input("Risk per trade (%)", 0.1, 10.0, 1.0, 0.1)
warmup = st.sidebar.slider("Warmup bars", 10, 120, 30)
max_hold_bars = st.sidebar.slider("Max hold bars", 5, 120, 30)


def screen_symbol(symbol: str) -> dict:
    provider = YFinanceProvider()
    df = provider.get_history(symbol, interval=interval, period=period, save_to_cache=True)
    result = research_dataframe(
        df=df,
        portfolio_size_sek=portfolio_size,
        risk_percent=risk_percent,
        warmup=warmup,
        max_hold_bars=max_hold_bars,
    )
    if result["status"] != "ok":
        candidate = candidate_filter_result("no_data", None, None)
        return {"symbol": symbol, "status": "no_data", "rank_score": 0, **candidate}

    current = result["current"]
    research = result["research"]
    summary = research["summary"]
    edge = research["edge"]
    confidence = current["confidence"]["score"]
    probability = research["probability"]
    total_r = summary.total_r
    rank = calculate_rank_components(
        confidence=confidence,
        historical_probability=probability,
        total_r=total_r,
        max_drawdown_r=summary.max_drawdown_r,
    )
    candidate = candidate_filter_result("ok", probability, total_r)

    return {
        "symbol": symbol,
        "status": "ok",
        "last": round(current["last_close"], 2),
        "setup": current["setup_label"],
        "signal": current["signal_label"],
        "confidence": confidence,
        "historical_probability": probability,
        "similar_samples": edge.sample_size,
        "matched_by": edge.match_description,
        "similar_win_rate": None if edge.win_rate is None else round(edge.win_rate, 3),
        "average_r": None if edge.average_r is None else round(edge.average_r, 3),
        "total_r": round(total_r, 3),
        "max_drawdown_r": round(summary.max_drawdown_r, 3),
        "confidence_contribution": rank["confidence_contribution"],
        "probability_contribution": rank["probability_contribution"],
        "total_r_contribution": rank["total_r_contribution"],
        "drawdown_penalty": rank["drawdown_penalty"],
        "decision": research["decision"],
        "rank_score": rank["rank_score"],
        **candidate,
    }


if st.sidebar.button("Run screener", type="primary"):
    symbols = [line.strip() for line in symbols_text.splitlines() if line.strip()]
    rows = []
    progress = st.progress(0)
    for idx, symbol in enumerate(symbols, start=1):
        rows.append(screen_symbol(symbol))
        progress.progress(idx / len(symbols))

    results = pd.DataFrame(rows).sort_values("rank_score", ascending=False)
    st.subheader("Ranked Results")
    st.dataframe(results, use_container_width=True, hide_index=True)

    candidates = results[results["candidate_pass"] == True]
    st.subheader("Higher-Quality Candidates")
    if candidates.empty:
        st.info("No symbols passed the candidate filter.")
    else:
        st.dataframe(candidates, use_container_width=True, hide_index=True)
else:
    st.info("Enter symbols, then run the screener.")
