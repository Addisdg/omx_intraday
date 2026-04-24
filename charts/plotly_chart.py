from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from analysis.indicators import add_indicators


def build_candlestick_chart(
    df: pd.DataFrame,
    supports: list[float],
    resistances: list[float],
    title: str = "Live Intraday Chart",
    ema_spans: list[int] | None = None,
    show_vwap: bool = False,
    show_atr_bands: bool = False,
    level_distance_percent: float | None = None,
    clean_mode: bool = False,
    height: int = 700,
) -> go.Figure:
    if clean_mode:
        show_vwap = False
        show_atr_bands = False
        ema_spans = [20]
        level_distance_percent = level_distance_percent or 2.0

    ema_spans = ema_spans or [20]
    work = add_indicators(
        df,
        ema_spans=ema_spans,
        include_vwap=show_vwap,
        include_atr_bands=show_atr_bands,
    )
    latest_close = float(work.iloc[-1]["close"])

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=work["timestamp"],
            open=work["open"],
            high=work["high"],
            low=work["low"],
            close=work["close"],
            name="Price",
        )
    )

    for span in ema_spans:
        column = f"ema{span}"
        fig.add_trace(
            go.Scatter(
                x=work["timestamp"],
                y=work[column],
                mode="lines",
                name=f"EMA{span}",
                line=dict(width=1.4 if span == 20 else 1.0),
            )
        )

    if show_vwap and "vwap" in work:
        fig.add_trace(
            go.Scatter(
                x=work["timestamp"],
                y=work["vwap"],
                mode="lines",
                name="VWAP",
                line=dict(dash="dot", width=1.1, color="#f59e0b"),
            )
        )

    if show_atr_bands and {"atr_upper", "atr_lower"}.issubset(work.columns):
        fig.add_trace(
            go.Scatter(
                x=work["timestamp"],
                y=work["atr_upper"],
                mode="lines",
                name="ATR upper",
                line=dict(width=0.8, dash="dot", color="rgba(248,113,113,0.55)"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=work["timestamp"],
                y=work["atr_lower"],
                mode="lines",
                name="ATR lower",
                line=dict(width=0.8, dash="dot", color="rgba(74,222,128,0.55)"),
            )
        )

    for level in _filter_levels(supports, latest_close, level_distance_percent):
        fig.add_hline(
            y=level,
            line_dash="dot",
            line_color="rgba(74,222,128,0.55)",
            annotation_text=f"S {level}",
            annotation_position="right",
        )

    for level in _filter_levels(resistances, latest_close, level_distance_percent):
        fig.add_hline(
            y=level,
            line_dash="dash",
            line_color="rgba(248,113,113,0.55)",
            annotation_text=f"R {level}",
            annotation_position="right",
        )

    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _filter_levels(
    levels: list[float],
    price: float,
    max_distance_percent: float | None,
) -> list[float]:
    if max_distance_percent is None or max_distance_percent <= 0:
        return levels
    max_distance = price * (max_distance_percent / 100)
    return [level for level in levels if abs(level - price) <= max_distance]
