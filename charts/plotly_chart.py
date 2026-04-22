from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def make_chart(
    df: pd.DataFrame,
    supports: list[float],
    resistances: list[float],
) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OMX",
        )
    )

    for s in supports:
        fig.add_hline(y=s, line_dash="dot", annotation_text=f"S {s}")

    for r in resistances:
        fig.add_hline(y=r, line_dash="dash", annotation_text=f"R {r}")

    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20).mean()

    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["ema20"],
            mode="lines",
            name="EMA20",
        )
    )

    fig.update_layout(
        title="OMX live dashboard",
        xaxis_rangeslider_visible=False,
        height=700,
    )
    return fig
