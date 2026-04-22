from __future__ import annotations

import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from data.provider_yfinance import YFinanceProvider
from analysis.levels import find_levels
from analysis.market_structure import classify_structure
from charts.plotly_chart import make_chart


st.set_page_config(page_title="OMX Live Analysis", layout="wide")
st.title("OMX Live Analysis")

symbol = st.sidebar.text_input("Symbol", value="AAPL")
interval = st.sidebar.selectbox("Interval", ["1m", "2m", "5m", "15m"], index=0)
refresh_seconds = st.sidebar.slider("Refresh seconds", 5, 60, 10)

# Proper refresh
st_autorefresh(interval=refresh_seconds * 1000, key="datarefresh")

provider = YFinanceProvider()

try:
    df = provider.get_intraday(symbol=symbol, interval=interval)

    st.subheader("Debug info")
    st.write(f"Rows returned: {len(df)}")
    if not df.empty:
        st.write(df.tail())

    if df.empty:
        st.warning(
            "No data returned. Try one of these symbols: AAPL, MSFT, NVDA, BTC-USD, ETH-USD, EURUSD=X"
        )
        st.stop()

    levels = find_levels(df, window=3, tolerance=1.5, min_touches=2)
    structure = classify_structure(df, lookback=min(20, len(df)))

    col1, col2 = st.columns([3, 1])

    with col1:
        fig = make_chart(
            df=df,
            supports=levels["supports"],
            resistances=levels["resistances"],
    )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        latest_close = float(df.iloc[-1]["close"])
        st.subheader("Market Read")
        st.write(f"**Structure:** {structure}")
        st.write(f"**Latest close:** {latest_close:.2f}")
        st.write(f"**Supports:** {levels['supports']}")
        st.write(f"**Resistances:** {levels['resistances']}")

except Exception as e:
    st.error(f"Update failed: {e}")