from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis.backtest import (
    equity_curve,
    optimize_parameters,
    replay_strategy,
    summarize_backtest,
    summarize_by_setup,
    validate_out_of_sample,
)
from data.cache import load_cached_data
from data.provider_yfinance import YFinanceProvider


st.set_page_config(page_title="Backtest", layout="wide")
st.title("Backtest Replay")
st.caption("Replay the current rule set candle by candle against cached or freshly downloaded data.")

symbol = st.sidebar.text_input("Symbol", value="^OMX")
interval = st.sidebar.selectbox("Interval", ["1m", "2m", "5m", "15m"], index=0)
source = st.sidebar.radio("Data source", ["Download latest", "Use local cache"], index=0)
portfolio_size = st.sidebar.number_input("Portfolio size", 1_000, 10_000_000, 30_000, 1_000)
risk_percent = st.sidebar.number_input("Risk per trade (%)", 0.1, 10.0, 1.0, 0.1)
warmup = st.sidebar.slider("Warmup bars", 10, 120, 30)
max_hold_bars = st.sidebar.slider("Max hold bars", 5, 180, 30)
prevent_overlaps = st.sidebar.checkbox("Prevent overlapping trades", value=True)
fee_per_trade = st.sidebar.number_input("Estimated fee per trade", 0.0, 10_000.0, 0.0, 1.0)
slippage_points = st.sidebar.number_input("Estimated slippage points", 0.0, 100.0, 0.0, 0.1)
start_text = st.sidebar.text_input("Start date/time (optional)", value="")
end_text = st.sidebar.text_input("End date/time (optional)", value="")
run_optimization = st.sidebar.checkbox("Run small parameter scan", value=False)
run_validation = st.sidebar.checkbox("Run out-of-sample split", value=True)
train_fraction = st.sidebar.slider("In-sample %", 50, 90, 70, 5) / 100


def _parse_optional_timestamp(value: str) -> pd.Timestamp | None:
    if not value.strip():
        return None
    return pd.Timestamp(value)


if st.sidebar.button("Run backtest", type="primary"):
    provider = YFinanceProvider()
    with st.spinner("Loading data and replaying strategy..."):
        if source == "Use local cache":
            df = load_cached_data(symbol, interval)
        else:
            df = provider.get_intraday(symbol, interval, save_to_cache=True)

        if df.empty:
            st.warning("No data available. Download latest data first or choose another symbol.")
            st.stop()

        start = _parse_optional_timestamp(start_text)
        end = _parse_optional_timestamp(end_text)
        trades = replay_strategy(
            df=df,
            portfolio_size_sek=portfolio_size,
            risk_percent=risk_percent,
            warmup=warmup,
            max_hold_bars=max_hold_bars,
            fee_per_trade=fee_per_trade,
            slippage_points=slippage_points,
            prevent_overlaps=prevent_overlaps,
            start=start,
            end=end,
        )
        summary = summarize_backtest(trades)
        validation = None
        if run_validation:
            validation = validate_out_of_sample(
                df=df,
                portfolio_size_sek=portfolio_size,
                risk_percent=risk_percent,
                warmup=warmup,
                max_hold_bars=max_hold_bars,
                train_fraction=train_fraction,
                fee_per_trade=fee_per_trade,
                slippage_points=slippage_points,
                prevent_overlaps=prevent_overlaps,
                start=start,
                end=end,
            )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades", summary.trades)
    c2.metric("Win rate", f"{summary.win_rate:.1%}")
    c3.metric("Total R", f"{summary.total_r:.2f}")
    c4.metric("Max drawdown R", f"{summary.max_drawdown_r:.2f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Wins", summary.wins)
    c6.metric("Losses", summary.losses)
    c7.metric("Open", summary.open_trades)
    c8.metric("Average R/R", "N/A" if summary.average_rr is None else f"{summary.average_rr:.2f}")

    if validation is not None:
        st.subheader("Out-Of-Sample Validation")
        st.caption(validation["verdict"])
        split_text = "N/A" if validation["split_timestamp"] is None else str(validation["split_timestamp"])
        st.write(
            f"Split at {split_text}; "
            f"{validation['in_sample_rows']} in-sample candles and "
            f"{validation['out_of_sample_rows']} out-of-sample candles."
        )

        in_summary = validation["in_sample_summary"]
        out_summary = validation["out_of_sample_summary"]
        validation_rows = pd.DataFrame(
            [
                {
                    "sample": "In-sample",
                    "trades": in_summary.trades,
                    "win_rate": in_summary.win_rate,
                    "total_r": in_summary.total_r,
                    "max_drawdown_r": in_summary.max_drawdown_r,
                },
                {
                    "sample": "Out-of-sample",
                    "trades": out_summary.trades,
                    "win_rate": out_summary.win_rate,
                    "total_r": out_summary.total_r,
                    "max_drawdown_r": out_summary.max_drawdown_r,
                },
            ]
        )
        st.dataframe(validation_rows, use_container_width=True, hide_index=True)

    if trades.empty:
        st.info("No qualifying setups were found in this replay.")
    else:
        curve = equity_curve(trades)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["timestamp"], y=curve["equity_r"], mode="lines", name="Equity R"))
        fig.add_trace(go.Scatter(x=curve["timestamp"], y=curve["drawdown_r"], mode="lines", name="Drawdown R"))
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
        st.subheader("Equity Curve")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Stats By Setup")
        st.dataframe(summarize_by_setup(trades), use_container_width=True, hide_index=True)

        st.subheader("Trades")
        st.dataframe(trades, use_container_width=True, hide_index=True)
        st.download_button(
            "Download trades CSV",
            data=trades.to_csv(index=False),
            file_name=f"{symbol}_{interval}_backtest.csv".replace("^", ""),
            mime="text/csv",
        )

    if run_optimization:
        st.subheader("Parameter Scan")
        scan = optimize_parameters(
            df=df,
            portfolio_size_sek=portfolio_size,
            risk_percent=risk_percent,
            warmup_values=[20, 30, 45, 60],
            max_hold_values=[10, 20, 30, 60],
            fee_per_trade=fee_per_trade,
            slippage_points=slippage_points,
        )
        st.dataframe(scan, use_container_width=True, hide_index=True)
else:
    st.info("Choose settings in the sidebar, then run the backtest.")
