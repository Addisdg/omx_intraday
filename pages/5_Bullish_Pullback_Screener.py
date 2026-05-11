from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.setup_filters import analyze_bullish_pullback_setup
from data.provider_base import provider_metadata_from_df
from data.provider_yfinance import YFinanceProvider


st.set_page_config(page_title="Bullish Pullback Screener", layout="wide")
st.title("Bullish Pullback Screener")
st.caption("Educational technical setup filter only; not financial advice.")

symbols_text = st.sidebar.text_area(
    "Symbols",
    value="AAPL\nMSFT\nNVDA\nSPY\nBTC-USD\nETH-USD\nEURUSD=X",
    height=180,
)
interval = st.sidebar.selectbox("Interval", ["1d", "60m", "30m", "15m"], index=0)
period = st.sidebar.selectbox("Period", ["1y", "2y", "5y"], index=1)
min_score = st.sidebar.slider("Minimum setup score", 0, 100, 70, 5)


def screen_symbol(symbol: str) -> dict:
    provider = YFinanceProvider()
    df = provider.get_history(symbol, interval=interval, period=period, save_to_cache=True)
    metadata = provider_metadata_from_df(df)
    setup = analyze_bullish_pullback_setup(df)
    return {
        "symbol": symbol,
        "provider": metadata["provider"],
        "source": metadata["source"],
        "rows": metadata["row_count"],
        "status": setup["status"],
        "candidate": setup["candidate"] and setup["score"] >= min_score,
        "score": setup["score"],
        "price": setup["price"],
        "sma50": setup["sma50"],
        "sma200": setup["sma200"],
        "rsi": setup["rsi"],
        "macd_histogram": setup["macd_histogram"],
        "relative_volume": setup["relative_volume"],
        "nearest_resistance": setup["nearest_resistance"],
        "suggested_stop": setup["suggested_stop"],
        "rr_to_resistance": setup["rr_to_resistance"],
        "passed": ", ".join(setup["passed_conditions"]),
        "failed": ", ".join(setup["failed_conditions"]),
        "reason": setup["reason"],
        "provider_warnings": "; ".join(metadata["warnings"]),
        **{name: detail["passed"] for name, detail in setup["conditions"].items()},
    }


def _available_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in df.columns]


if st.sidebar.button("Run bullish pullback screen", type="primary"):
    symbols = [line.strip() for line in symbols_text.splitlines() if line.strip()]
    if not symbols:
        st.warning("Enter at least one symbol.")
        st.stop()

    rows = []
    progress = st.progress(0)
    status_line = st.empty()
    for idx, symbol in enumerate(symbols, start=1):
        status_line.caption(f"Screening {symbol} ({idx}/{len(symbols)})")
        try:
            rows.append(screen_symbol(symbol))
        except Exception as exc:
            rows.append(
                {
                    "symbol": symbol,
                    "status": "error",
                    "candidate": False,
                    "score": 0,
                    "reason": str(exc),
                }
            )
        progress.progress(idx / len(symbols))

    results = pd.DataFrame(rows).sort_values(["candidate", "score"], ascending=[False, False])
    candidates = results[results["candidate"] == True]

    candidates_tab, all_tab, failed_tab = st.tabs(["Candidates", "All Results", "Failed Conditions"])

    with candidates_tab:
        st.subheader("Bullish Pullback Candidates")
        if candidates.empty:
            st.info("No symbols met the minimum setup score.")
        else:
            st.dataframe(
                candidates[
                    [
                        "symbol",
                        "score",
                        "price",
                        "rsi",
                        "macd_histogram",
                        "relative_volume",
                        "nearest_resistance",
                        "rr_to_resistance",
                        "reason",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with all_tab:
        st.subheader("All Screened Symbols")
        st.dataframe(results, use_container_width=True, hide_index=True)

    with failed_tab:
        st.subheader("Failed Or Missing Conditions")
        st.dataframe(
            results[
                _available_columns(
                    results,
                    ["symbol", "score", "failed", "reason", "provider", "source", "provider_warnings"],
                )
            ],
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("Enter symbols, choose a market timeframe, then run the bullish pullback screen.")
