from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def build_candlestick_chart(
    df: pd.DataFrame,
    supports: list[float],
    resistances: list[float],
    title: str = "Live Intraday Chart",
) -> go.Figure:
    work = df.copy()
    work["ema20"] = work["close"].ewm(span=20).mean()

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

    fig.add_trace(
        go.Scatter(
            x=work["timestamp"],
            y=work["ema20"],
            mode="lines",
            name="EMA20",
        )
    )

    for level in supports:
        fig.add_hline(
            y=level,
            line_dash="dot",
            annotation_text=f"S {level}",
            annotation_position="right",
        )

    for level in resistances:
        fig.add_hline(
            y=level,
            line_dash="dash",
            annotation_text=f"R {level}",
            annotation_position="right",
        )

    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        height=700,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig