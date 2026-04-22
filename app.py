from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from data.provider_yfinance import YFinanceProvider
from analysis.levels import find_levels
from analysis.market_structure import classify_structure
from analysis.signals import classify_signal
from charts.plotly_chart import build_candlestick_chart
from analysis.trade_engine import build_trade_plan


st.set_page_config(page_title="OMX Live Analysis", layout="wide")
st.title("OMX Live Analysis")

symbol = st.sidebar.text_input("Symbol", value="^OMX")
interval = st.sidebar.selectbox("Interval", ["1m", "2m", "5m", "15m"], index=0)
refresh_seconds = st.sidebar.slider("Refresh seconds", 5, 60, 10)

preset = st.sidebar.selectbox(
    "Quick presets",
    ["Custom", "AAPL", "MSFT", "NVDA", "SPY", "BTC-USD", "ETH-USD", "EURUSD=X"],
    index=0,
)
if preset != "Custom":
    symbol = preset

st_autorefresh(interval=refresh_seconds * 1000, key="datarefresh")

provider = YFinanceProvider()

try:
    df = provider.get_intraday(symbol=symbol, interval=interval)

    if df.empty:
        st.warning(
            "No data returned. Try AAPL, MSFT, NVDA, SPY, BTC-USD, ETH-USD, EURUSD=X."
        )
        st.stop()

    levels = find_levels(df, window=3, tolerance=1.5, min_touches=2)
    structure = classify_structure(df, lookback=min(30, len(df)))
    signal = classify_signal(df, levels["supports"], levels["resistances"], structure)
    trade_plan = build_trade_plan(
    df=df,
    structure=structure,
    supports=levels["supports"],
    resistances=levels["resistances"],
    portfolio_size_sek=30000,
    risk_percent=1.0,
    )

    latest_close = float(df.iloc[-1]["close"])
    latest_open = float(df.iloc[-1]["open"])
    latest_high = float(df.iloc[-1]["high"])
    latest_low = float(df.iloc[-1]["low"])

    c1, c2 = st.columns([4, 1])

    with c1:
        fig = build_candlestick_chart(
            df=df,
            supports=levels["supports"],
            resistances=levels["resistances"],
            title=f"{symbol} live dashboard",
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Market Read")
        st.write(f"**Structure:** {structure}")
        st.write(f"**Latest close:** {latest_close:.2f}")
        st.write(f"**Latest open:** {latest_open:.2f}")
        st.write(f"**Day high:** {latest_high:.2f}")
        st.write(f"**Day low:** {latest_low:.2f}")

        st.write(f"**Supports:** {levels['supports']}")
        st.write(f"**Resistances:** {levels['resistances']}")

        nearest_support = signal["nearest_support"]
        nearest_resistance = signal["nearest_resistance"]

        if nearest_support is None:
            st.write("**Nearest support:** Below all detected support")
        else:
            st.write(f"**Nearest support:** {nearest_support}")

        if nearest_resistance is None:
            if len(levels["resistances"]) > 0 and latest_close > max(levels["resistances"]):
                st.write("**Nearest resistance:** Above detected range")
            else:
                st.write("**Nearest resistance:** None")
        else:
            st.write(f"**Nearest resistance:** {nearest_resistance}")

        st.write(f"**Signal:** {signal['signal']}")
        st.write(f"**Reason:** {signal['reason']}")
        st.subheader("Trade Engine")
        st.write(f"**Bias:** {trade_plan.bias}")
        st.write(f"**Setup:** {trade_plan.setup}")
        st.write(f"**Entry:** {trade_plan.entry}")
        st.write(f"**Stop loss:** {trade_plan.stop_loss}")
        st.write(f"**Target:** {trade_plan.target}")
        st.write(f"**Risk/share:** {trade_plan.risk_per_share}")
        st.write(f"**Reward/share:** {trade_plan.reward_per_share}")
        st.write(f"**R/R ratio:** {trade_plan.rr_ratio}")
        st.write(f"**Position size (shares):** {trade_plan.position_size_shares}")
        st.write(f"**Position value:** {trade_plan.position_size_value}")
        st.write(f"**Why:** {trade_plan.reason}")

except Exception as e:
    st.error(f"Update failed: {e}")