from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.confidence import score_setup
from analysis.levels import find_levels
from analysis.market_hours import format_timestamp, market_status
from analysis.market_structure import classify_structure
from analysis.signals import classify_signal
from analysis.trade_engine import build_trade_plan
from analysis.volume import analyze_volume
from config.settings import load_settings, save_settings
from data.provider_yfinance import YFinanceProvider
from ui.labels import setup_label, signal_label


st.set_page_config(page_title="Watchlist", layout="wide")
st.title("Watchlist Scanner")
st.caption("Scan multiple symbols with the same market-read and trade-engine rules.")

settings = load_settings()
symbols_text = st.sidebar.text_area("Symbols", value=settings["watchlist"], height=180)
interval = st.sidebar.selectbox("Interval", ["1m", "2m", "5m", "15m"], index=2)
portfolio_size = st.sidebar.number_input("Portfolio size", 1_000, 10_000_000, int(settings["portfolio_size"]), 1_000)
risk_percent = st.sidebar.number_input("Risk per trade (%)", 0.1, 10.0, float(settings["risk_percent"]), 0.1)
fee_per_trade = st.sidebar.number_input("Estimated fee per trade", 0.0, 10_000.0, float(settings["fee_per_trade"]), 1.0)
slippage_points = st.sidebar.number_input("Estimated slippage points", 0.0, 100.0, float(settings["slippage_points"]), 0.1)
timezone = st.sidebar.selectbox("Display timezone", ["Europe/Stockholm", "UTC", "America/New_York"])

if st.sidebar.button("Save watchlist"):
    save_settings({**settings, "watchlist": symbols_text})
    st.sidebar.success("Watchlist saved")


def scan_symbol(symbol: str) -> dict:
    provider = YFinanceProvider()
    df = provider.get_intraday(symbol, interval, save_to_cache=True)
    if df.empty:
        return {"symbol": symbol, "status": "no_data", "setup": "no_data", "raw_setup": "no_data"}

    levels = find_levels(df, window=3, tolerance=None, min_touches=2)
    structure = classify_structure(df, lookback=min(30, len(df)))
    signal = classify_signal(df, levels["supports"], levels["resistances"], structure)
    volume_read = analyze_volume(df)
    plan = build_trade_plan(
        df=df,
        structure=structure,
        supports=levels["supports"],
        resistances=levels["resistances"],
        portfolio_size_sek=portfolio_size,
        risk_percent=risk_percent,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
    )
    confidence = score_setup(df, structure, signal, plan, levels["supports"], levels["resistances"], volume_read)

    return {
        "symbol": symbol,
        "last": round(float(df.iloc[-1]["close"]), 2),
        "last_candle": format_timestamp(df.iloc[-1]["timestamp"], timezone),
        "market": market_status(symbol),
        "structure": structure,
        "signal": signal_label(signal["signal"]),
        "setup": setup_label(plan.setup),
        "raw_setup": plan.setup,
        "bias": plan.bias,
        "confidence": confidence["score"],
        "volume": volume_read["volume_state"],
        "relative_volume": volume_read["relative_volume"],
        "entry": plan.entry,
        "stop": plan.stop_loss,
        "target": plan.target,
        "rr": plan.rr_ratio,
        "position_size": plan.position_size_shares,
        "reason": plan.reason,
    }


if st.sidebar.button("Scan watchlist", type="primary"):
    symbols = [line.strip() for line in symbols_text.splitlines() if line.strip()]
    rows = []
    progress = st.progress(0)
    for idx, symbol in enumerate(symbols, start=1):
        rows.append(scan_symbol(symbol))
        progress.progress(idx / len(symbols))

    results = pd.DataFrame(rows)
    active = results[~results["raw_setup"].isin(["WAIT", "SKIP", "NONE", "no_data"])] if "raw_setup" in results else pd.DataFrame()

    st.subheader("Active Setups")
    if active.empty:
        st.info("No active setups found.")
    else:
        st.dataframe(active.drop(columns=["raw_setup"]), use_container_width=True, hide_index=True)

    st.subheader("Full Watchlist")
    if "raw_setup" in results:
        results = results.drop(columns=["raw_setup"])
    st.dataframe(results, use_container_width=True, hide_index=True)
else:
    st.info("Enter symbols in the sidebar, then scan the watchlist.")
