from __future__ import annotations

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from analysis.confidence import score_setup
from analysis.data_quality import assess_data_quality
from analysis.indicators import summarize_indicator_context
from analysis.levels import find_levels
from analysis.market_hours import format_timestamp, market_status
from analysis.market_structure import classify_structure
from analysis.signals import classify_signal
from analysis.timeframes import build_timeframe_confirmation
from analysis.trade_engine import build_trade_plan
from analysis.volatility import analyze_volatility_regime
from analysis.volume import analyze_volume
from charts.plotly_chart import build_candlestick_chart
from config.settings import load_settings, save_settings
from data.provider_yfinance import YFinanceProvider
from ui.labels import setup_label, signal_label


INTERVALS = ["1m", "2m", "5m", "15m"]
CONFIRMATION_INTERVALS = ["None", "15m", "30m", "60m", "1d"]
TIMEZONES = ["Europe/Stockholm", "UTC", "America/New_York"]
EMA_OPTIONS = [9, 20, 50, 200]
PRESETS = ["Custom", "^OMX", "AAPL", "MSFT", "NVDA", "SPY", "BTC-USD", "ETH-USD", "EURUSD=X"]


def _fmt(value: object) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _nearest_support_text(value: float | None) -> str:
    return "Below all detected support" if value is None else str(value)


def _nearest_resistance_text(value: float | None, resistances: list[float], price: float) -> str:
    if value is not None:
        return str(value)
    if resistances and price > max(resistances):
        return "Above detected range"
    return "None"


st.set_page_config(page_title="OMX Live Analysis", layout="wide")
st.title("OMX Live Analysis")
st.caption("Educational market analysis only; not financial advice.")

settings = load_settings()

if "symbol_input" not in st.session_state:
    st.session_state.symbol_input = settings["symbol"]
if "preset_choice" not in st.session_state:
    st.session_state.preset_choice = "Custom"


def _apply_preset_choice() -> None:
    if st.session_state.preset_choice != "Custom":
        st.session_state.symbol_input = st.session_state.preset_choice


symbol = st.sidebar.text_input("Symbol", key="symbol_input")
interval = st.sidebar.selectbox(
    "Interval",
    INTERVALS,
    index=INTERVALS.index(settings["interval"]) if settings["interval"] in INTERVALS else 0,
)
confirmation_interval = st.sidebar.selectbox(
    "Confirmation timeframe",
    CONFIRMATION_INTERVALS,
    index=(
        CONFIRMATION_INTERVALS.index(settings["confirmation_interval"])
        if settings["confirmation_interval"] in CONFIRMATION_INTERVALS
        else 0
    ),
)
refresh_seconds = st.sidebar.slider("Refresh seconds", 5, 60, int(settings["refresh_seconds"]))
portfolio_size_sek = st.sidebar.number_input(
    "Portfolio size",
    min_value=1_000,
    max_value=10_000_000,
    value=int(settings["portfolio_size"]),
    step=1_000,
)
risk_percent = st.sidebar.number_input(
    "Risk per trade (%)",
    min_value=0.1,
    max_value=10.0,
    value=float(settings["risk_percent"]),
    step=0.1,
)
fee_per_trade = st.sidebar.number_input(
    "Estimated fee per trade",
    min_value=0.0,
    max_value=10_000.0,
    value=float(settings["fee_per_trade"]),
    step=1.0,
)
slippage_points = st.sidebar.number_input(
    "Estimated slippage points",
    min_value=0.0,
    max_value=100.0,
    value=float(settings["slippage_points"]),
    step=0.1,
)
timezone = st.sidebar.selectbox(
    "Display timezone",
    TIMEZONES,
    index=TIMEZONES.index(settings["timezone"]) if settings["timezone"] in TIMEZONES else 0,
)
clean_chart_mode = st.sidebar.checkbox("Clean chart mode", value=bool(settings["clean_chart_mode"]))
ema_spans = st.sidebar.multiselect(
    "Moving averages",
    EMA_OPTIONS,
    default=[span for span in settings["ema_spans"] if span in EMA_OPTIONS] or [20],
    disabled=clean_chart_mode,
)
show_vwap = st.sidebar.checkbox("Show VWAP", value=bool(settings["show_vwap"]), disabled=clean_chart_mode)
show_atr_bands = st.sidebar.checkbox(
    "Show ATR bands", value=bool(settings["show_atr_bands"]), disabled=clean_chart_mode
)
show_indicator_context = st.sidebar.checkbox(
    "Show indicator context", value=bool(settings["show_indicator_context"])
)
level_distance_percent = st.sidebar.slider(
    "Show levels within % of price",
    min_value=0.0,
    max_value=10.0,
    value=float(settings["level_distance_percent"]),
    step=0.5,
    help="Use 0 to show all detected levels.",
)
enable_alerts = st.sidebar.checkbox("Enable setup alerts", value=bool(settings["enable_alerts"]))
show_debug = st.sidebar.checkbox("Show debug errors", value=False)

st.sidebar.selectbox("Quick presets", PRESETS, key="preset_choice")
st.sidebar.button("Apply preset", on_click=_apply_preset_choice)

if st.sidebar.button("Save current settings"):
    save_settings(
        {
            "symbol": symbol,
            "interval": interval,
            "refresh_seconds": refresh_seconds,
            "portfolio_size": portfolio_size_sek,
            "risk_percent": risk_percent,
            "fee_per_trade": fee_per_trade,
            "slippage_points": slippage_points,
            "timezone": timezone,
            "ema_spans": ema_spans or [20],
            "show_vwap": show_vwap,
            "show_atr_bands": show_atr_bands,
            "show_indicator_context": show_indicator_context,
            "clean_chart_mode": clean_chart_mode,
            "level_distance_percent": level_distance_percent,
            "enable_alerts": enable_alerts,
            "confirmation_interval": confirmation_interval,
            "watchlist": settings["watchlist"],
        }
    )
    st.sidebar.success("Settings saved")

st_autorefresh(interval=refresh_seconds * 1000, key="datarefresh")

provider = YFinanceProvider()

try:
    df = provider.get_intraday(symbol=symbol, interval=interval)

    if df.empty:
        st.warning("No data returned. Try AAPL, MSFT, NVDA, SPY, BTC-USD, ETH-USD, EURUSD=X.")
        st.stop()

    data_quality = assess_data_quality(df)
    if data_quality["status"] == "invalid":
        st.error(data_quality["summary"])
        for issue in data_quality["issues"]:
            st.warning(issue)
        st.stop()

    levels = find_levels(df, window=3, tolerance=None, min_touches=2)
    structure = classify_structure(df, lookback=min(30, len(df)))
    signal = classify_signal(df, levels["supports"], levels["resistances"], structure)
    volume_read = analyze_volume(df)
    volatility_read = analyze_volatility_regime(df)
    indicator_context = summarize_indicator_context(df)
    timeframe_confirmation = None
    if confirmation_interval != "None":
        confirmation_df = provider.get_history(
            symbol=symbol,
            interval=confirmation_interval,
            period="1y" if confirmation_interval == "1d" else "1mo",
            save_to_cache=True,
        )
        timeframe_confirmation = build_timeframe_confirmation(
            lower_structure=structure,
            higher_df=confirmation_df,
            higher_interval=confirmation_interval,
        )
    trade_plan = build_trade_plan(
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
        trade_plan,
        levels["supports"],
        levels["resistances"],
        volume_read,
        timeframe_confirmation=timeframe_confirmation,
        volatility_regime=volatility_read,
        indicator_context=indicator_context,
    )

    latest_close = float(df.iloc[-1]["close"])
    latest_open = float(df.iloc[-1]["open"])
    session_high = float(df["high"].max())
    session_low = float(df["low"].min())
    latest_timestamp = format_timestamp(df.iloc[-1]["timestamp"], timezone)

    chart_col, read_col = st.columns([3.8, 1.2])

    with chart_col:
        chart_height = 620 if clean_chart_mode else 740
        fig = build_candlestick_chart(
            df=df,
            supports=levels["supports"],
            resistances=levels["resistances"],
            title=f"{symbol} live dashboard",
            ema_spans=ema_spans or [20],
            show_vwap=show_vwap,
            show_atr_bands=show_atr_bands,
            level_distance_percent=level_distance_percent,
            clean_mode=clean_chart_mode,
            height=chart_height,
        )
        st.plotly_chart(fig, use_container_width=True)

    with read_col:
        st.subheader("Market Read")
        st.caption(f"Last candle: {latest_timestamp}")
        st.caption(market_status(symbol))
        st.caption("Data source: yfinance intraday data, which may be delayed.")
        if data_quality["status"] == "ok":
            st.caption(f"Data quality: {data_quality['summary']} ({data_quality['row_count']} candles)")
        else:
            st.warning(f"Data quality: {data_quality['summary']}")
            with st.expander("Data quality details", expanded=False):
                st.write(f"**Rows:** {data_quality['row_count']}")
                st.write(f"**First candle:** {data_quality['first_timestamp']}")
                st.write(f"**Last candle:** {data_quality['last_timestamp']}")
                for issue in data_quality["issues"]:
                    st.write(f"- {issue}")

        price_card, signal_card = st.columns(2)
        price_card.metric("Last", f"{latest_close:.2f}", f"Open {latest_open:.2f}")
        signal_card.metric("Confidence", f"{confidence['score']}/100", confidence["grade"])

        st.info(f"Structure: {structure}")
        if timeframe_confirmation is not None:
            status = timeframe_confirmation["status"].replace("_", " ").title()
            st.write(f"**Timeframe confirmation:** {status}")
            st.caption(timeframe_confirmation["reason"])
        st.write(f"**Signal:** {signal_label(signal['signal'])}")
        st.write(f"**Reason:** {signal['reason']}")

        with st.expander("Price levels", expanded=False):
            st.write(f"**Session high:** {session_high:.2f}")
            st.write(f"**Session low:** {session_low:.2f}")
            st.write(f"**Supports:** {levels['supports']}")
            st.write(f"**Resistances:** {levels['resistances']}")
            st.write(f"**Nearest support:** {_nearest_support_text(signal['nearest_support'])}")
            st.write(f"**Nearest resistance:** {_nearest_resistance_text(signal['nearest_resistance'], levels['resistances'], latest_close)}")

        with st.expander("Volume context", expanded=True):
            st.write(f"**State:** {volume_read['volume_state']}")
            st.write(f"**Relative volume:** {volume_read['relative_volume']}")
            st.write(f"**Latest volume:** {volume_read['latest_volume']}")
            st.write(f"**Average volume:** {volume_read['average_volume']}")
            st.caption(volume_read["reason"])

        with st.expander("Volatility context", expanded=False):
            st.write(f"**State:** {volatility_read['volatility_state']}")
            st.write(f"**ATR ratio:** {volatility_read['atr_ratio']}")
            st.write(f"**Current ATR:** {_fmt(volatility_read['current_atr'])}")
            st.write(f"**Baseline ATR:** {_fmt(volatility_read['baseline_atr'])}")
            st.caption(volatility_read["reason"])

        if show_indicator_context:
            with st.expander("Indicator context", expanded=False):
                st.write(f"**Status:** {indicator_context['status']}")
                st.write(f"**RSI:** {_fmt(indicator_context['rsi'])} ({indicator_context['rsi_state']})")
                st.write(f"**MACD:** {indicator_context['macd_state']}")
                st.write(f"**MACD histogram:** {_fmt(indicator_context['macd_histogram'])}")
                st.write(f"**Bollinger position:** {indicator_context['bollinger_state']}")
                st.write(f"**EMA20 slope:** {_fmt(indicator_context['ema20_slope_percent'])}%")
                st.caption(indicator_context["reason"])

        st.subheader("Trade Engine")
        if trade_plan.bias == "BULLISH":
            st.success(f"Bias: {trade_plan.bias}")
        elif trade_plan.bias == "BEARISH":
            st.error(f"Bias: {trade_plan.bias}")
        else:
            st.info(f"Bias: {trade_plan.bias}")

        st.write(f"**Setup:** {setup_label(trade_plan.setup)}")
        trade_metrics = st.columns(2)
        trade_metrics[0].metric("Entry", _fmt(trade_plan.entry))
        trade_metrics[1].metric("R/R", _fmt(trade_plan.rr_ratio))
        st.write(f"**Stop loss:** {_fmt(trade_plan.stop_loss)}")
        st.write(f"**Target:** {_fmt(trade_plan.target)}")
        st.write(f"**Risk/share:** {_fmt(trade_plan.risk_per_share)}")
        st.write(f"**Reward/share:** {_fmt(trade_plan.reward_per_share)}")
        st.write(f"**Position size:** {_fmt(trade_plan.position_size_shares)}")
        st.write(f"**Position value:** {_fmt(trade_plan.position_size_value)}")
        st.caption(trade_plan.reason)

        with st.expander("Confidence details", expanded=False):
            factor_rows = [
                {
                    "Factor": name.replace("_", " ").title(),
                    "Score": f"{factor['score']}/{factor['max_score']}",
                    "Reason": factor["reason"],
                }
                for name, factor in confidence.get("factors", {}).items()
            ]
            if factor_rows:
                st.dataframe(factor_rows, use_container_width=True, hide_index=True)
            else:
                st.write(confidence["components"])
            if confidence.get("cap_applied"):
                st.caption(f"Raw score {confidence['raw_score']} was capped because no actionable setup is active.")
            for note in confidence["notes"]:
                st.caption(note)

        if enable_alerts and trade_plan.setup not in {"WAIT", "SKIP", "NONE"}:
            st.warning(f"Scenario alert: {setup_label(trade_plan.setup)} on {symbol}")

except Exception as e:
    st.error(f"Update failed: {e}")
    if "show_debug" in locals() and show_debug:
        st.exception(e)
