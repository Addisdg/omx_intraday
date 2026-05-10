from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from analysis.backtest import equity_curve
from data.cache import load_cached_data
from data.provider_yfinance import YFinanceProvider
from services.market_analysis import research_dataframe


st.set_page_config(page_title="Historical Research", layout="wide")
st.title("Historical Research")
st.caption("Compare the current setup with historical replay results and show probability-style output.")

symbol = st.sidebar.text_input("Symbol", value="AAPL")
interval = st.sidebar.selectbox("Interval", ["1m", "5m", "15m", "30m", "60m", "1d"], index=2)
period = st.sidebar.selectbox("Period", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
source = st.sidebar.radio("Data source", ["Download latest", "Use local cache"], index=0)
portfolio_size = st.sidebar.number_input("Portfolio size", 1_000, 10_000_000, 30_000, 1_000)
risk_percent = st.sidebar.number_input("Risk per trade (%)", 0.1, 10.0, 1.0, 0.1)
warmup = st.sidebar.slider("Warmup bars", 10, 180, 30)
max_hold_bars = st.sidebar.slider("Max hold bars", 5, 240, 30)
run_validation = st.sidebar.checkbox("Run out-of-sample split", value=True)
train_fraction = st.sidebar.slider("In-sample %", 50, 90, 70, 5) / 100
fee_per_trade = st.sidebar.number_input("Estimated fee per trade", 0.0, 10_000.0, 0.0, 1.0)
slippage_points = st.sidebar.number_input("Estimated slippage points", 0.0, 100.0, 0.0, 0.1)

if st.sidebar.button("Run research", type="primary"):
    provider = YFinanceProvider()
    with st.spinner("Loading history and running research replay..."):
        if source == "Use local cache":
            df = load_cached_data(symbol, interval)
        else:
            df = provider.get_history(symbol, interval=interval, period=period, save_to_cache=True)

        result = research_dataframe(
            df=df,
            portfolio_size_sek=portfolio_size,
            risk_percent=risk_percent,
            warmup=warmup,
            max_hold_bars=max_hold_bars,
            train_fraction=train_fraction if run_validation else None,
            fee_per_trade=fee_per_trade,
            slippage_points=slippage_points,
        )

    if result["status"] != "ok":
        st.warning("No usable data found for this research run.")
        st.stop()

    current = result["current"]
    research = result["research"]
    summary = research["summary"]
    edge = research["edge"]
    quality = research["quality"]
    trades = research["trades"]
    validation = research["validation"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current confidence", f"{current['confidence']['score']}/100", current["confidence"]["grade"])
    c2.metric("Historical probability", f"{research['probability']}%")
    c3.metric("Similar samples", edge.sample_size)
    c4.metric("Decision", research["decision"])

    st.subheader("Current Setup")
    st.write(f"**Symbol:** {symbol}")
    st.write(f"**Signal:** {current['signal_label']}")
    st.write(f"**Setup scenario:** {current['setup_label']}")
    st.write(f"**Structure:** {current['structure']}")
    st.write(f"**Volume:** {current['volume']['volume_state']} ({current['volume']['relative_volume']}x)")

    st.subheader("Research Quality")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Quality", quality["quality"])
    q2.metric("Matched samples", f"{quality['sample_size']}/{quality['minimum_sample']} min")
    q3.metric("Replay trades", quality["total_replayed_trades"])
    q4.metric("Validation", quality["validation_status"].replace("_", " ").title())
    st.caption(quality["reason"])
    with st.expander("Research quality details", expanded=False):
        st.write(f"**Fallback level:** {quality['fallback_level'].replace('_', ' ')}")
        st.write(f"**Matched by:** {quality['match_description']}")
        st.write(
            "**Requested dimensions:** "
            + (", ".join(quality["requested_dimensions"]) if quality["requested_dimensions"] else "setup only")
        )
        st.write(
            "**Matched dimensions:** "
            + (", ".join(quality["matched_dimensions"]) if quality["matched_dimensions"] else "setup only")
        )
        for warning in quality["warnings"]:
            st.warning(warning)

    st.subheader("Historical Edge For Similar Setup")
    st.write(f"**Verdict:** {edge.verdict}")
    st.write(f"**Win rate:** {'N/A' if edge.win_rate is None else f'{edge.win_rate:.1%}'}")
    st.write(f"**Average R:** {'N/A' if edge.average_r is None else f'{edge.average_r:.2f}'}")
    st.write(f"**Total R:** {'N/A' if edge.total_r is None else f'{edge.total_r:.2f}'}")
    st.write(f"**Matched by:** {edge.match_description}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("All trades", summary.trades)
    c6.metric("All win rate", f"{summary.win_rate:.1%}")
    c7.metric("All total R", f"{summary.total_r:.2f}")
    c8.metric("Max drawdown R", f"{summary.max_drawdown_r:.2f}")

    if validation is not None:
        st.subheader("Out-Of-Sample Validation")
        st.caption(validation["verdict"])
        in_summary = validation["in_sample_summary"]
        out_summary = validation["out_of_sample_summary"]
        c9, c10, c11, c12 = st.columns(4)
        c9.metric("In-sample R", f"{in_summary.total_r:.2f}")
        c10.metric("Out-of-sample R", f"{out_summary.total_r:.2f}")
        c11.metric("Out-of-sample trades", out_summary.trades)
        c12.metric("Split", f"{validation['train_fraction']:.0%}")

    if not trades.empty:
        curve = equity_curve(trades)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=curve["timestamp"], y=curve["equity_r"], mode="lines", name="Equity R"))
        fig.add_trace(go.Scatter(x=curve["timestamp"], y=curve["drawdown_r"], mode="lines", name="Drawdown R"))
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
        st.subheader("Research Equity Curve")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Performance By Setup")
        st.dataframe(research["by_setup"], use_container_width=True, hide_index=True)

        st.subheader("Historical Trades")
        st.dataframe(trades, use_container_width=True, hide_index=True)
else:
    st.info("Choose a symbol and settings, then run historical research.")
