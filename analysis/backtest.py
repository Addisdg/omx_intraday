from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from analysis.levels import find_levels
from analysis.market_structure import classify_structure
from analysis.trade_engine import TradePlan, build_trade_plan


@dataclass(frozen=True)
class BacktestSummary:
    trades: int
    wins: int
    losses: int
    open_trades: int
    win_rate: float
    average_rr: float | None
    total_r: float
    max_drawdown_r: float


def replay_strategy(
    df: pd.DataFrame,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    warmup: int = 30,
    max_hold_bars: int = 30,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
    prevent_overlaps: bool = True,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    records: list[dict] = []
    df = _filter_date_range(df, start, end)
    if df.empty or len(df) <= warmup:
        return pd.DataFrame()

    idx = warmup
    while idx < len(df) - 1:
        history = df.iloc[: idx + 1].reset_index(drop=True)
        levels = find_levels(history, window=3, tolerance=None, min_touches=2)
        structure = classify_structure(history, lookback=min(30, len(history)))
        plan = build_trade_plan(
            df=history,
            structure=structure,
            supports=levels["supports"],
            resistances=levels["resistances"],
            portfolio_size_sek=portfolio_size_sek,
            risk_percent=risk_percent,
            fee_per_trade=fee_per_trade,
            slippage_points=slippage_points,
        )

        if plan.bias not in {"BULLISH", "BEARISH"} or plan.entry is None:
            idx += 1
            continue

        outcome = _resolve_trade(
            plan=plan,
            future=df.iloc[idx + 1 : idx + 1 + max_hold_bars],
            fee_per_trade=fee_per_trade,
            slippage_points=slippage_points,
        )
        records.append(
            {
                "timestamp": history.iloc[-1]["timestamp"],
                "bias": plan.bias,
                "setup": plan.setup,
                "entry": plan.entry,
                "stop_loss": plan.stop_loss,
                "target": plan.target,
                "rr_ratio": plan.rr_ratio,
                "position_size": plan.position_size_shares,
                "outcome": outcome["outcome"],
                "bars_held": outcome["bars_held"],
                "r_multiple": outcome["r_multiple"],
                "exit_price": outcome["exit_price"],
                "reason": plan.reason,
            }
        )
        if prevent_overlaps:
            idx += max(1, int(outcome["bars_held"]))
        else:
            idx += 1

    return pd.DataFrame(records)


def summarize_backtest(trades: pd.DataFrame) -> BacktestSummary:
    if trades.empty:
        return BacktestSummary(0, 0, 0, 0, 0.0, None, 0.0, 0.0)

    closed = trades[trades["outcome"].isin(["target", "stop", "timeout"])]
    wins = int((closed["r_multiple"] > 0).sum())
    losses = int((closed["r_multiple"] < 0).sum())
    open_trades = int((trades["outcome"] == "open").sum())
    total = int(len(closed))
    win_rate = wins / total if total else 0.0
    average_rr = float(closed["rr_ratio"].dropna().mean()) if not closed.empty else None
    equity_r = closed["r_multiple"].fillna(0).cumsum()
    drawdown = equity_r - equity_r.cummax()

    return BacktestSummary(
        trades=int(len(trades)),
        wins=wins,
        losses=losses,
        open_trades=open_trades,
        win_rate=win_rate,
        average_rr=average_rr,
        total_r=float(closed["r_multiple"].fillna(0).sum()),
        max_drawdown_r=float(drawdown.min()) if not drawdown.empty else 0.0,
    )


def equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["timestamp", "equity_r", "drawdown_r"])

    curve = trades.copy()
    curve["equity_r"] = curve["r_multiple"].fillna(0).cumsum()
    curve["drawdown_r"] = curve["equity_r"] - curve["equity_r"].cummax()
    return curve[["timestamp", "equity_r", "drawdown_r"]]


def summarize_by_setup(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["setup", "trades", "win_rate", "average_r", "total_r"])

    grouped = []
    for setup, group in trades.groupby("setup"):
        closed = group[group["outcome"].isin(["target", "stop", "timeout"])]
        wins = int((closed["r_multiple"] > 0).sum())
        total = len(closed)
        grouped.append(
            {
                "setup": setup,
                "trades": len(group),
                "win_rate": wins / total if total else 0.0,
                "average_r": float(closed["r_multiple"].mean()) if total else 0.0,
                "total_r": float(closed["r_multiple"].sum()) if total else 0.0,
            }
        )
    return pd.DataFrame(grouped).sort_values("total_r", ascending=False).reset_index(drop=True)


def optimize_parameters(
    df: pd.DataFrame,
    portfolio_size_sek: float,
    risk_percent: float,
    max_hold_values: list[int],
    warmup_values: list[int],
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
) -> pd.DataFrame:
    rows = []
    for warmup in warmup_values:
        for max_hold_bars in max_hold_values:
            trades = replay_strategy(
                df=df,
                portfolio_size_sek=portfolio_size_sek,
                risk_percent=risk_percent,
                warmup=warmup,
                max_hold_bars=max_hold_bars,
                fee_per_trade=fee_per_trade,
                slippage_points=slippage_points,
                prevent_overlaps=True,
            )
            summary = summarize_backtest(trades)
            rows.append(
                {
                    "warmup": warmup,
                    "max_hold_bars": max_hold_bars,
                    "trades": summary.trades,
                    "win_rate": summary.win_rate,
                    "total_r": summary.total_r,
                    "max_drawdown_r": summary.max_drawdown_r,
                    "score": summary.total_r + summary.max_drawdown_r,
                }
            )
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


def _resolve_trade(
    plan: TradePlan,
    future: pd.DataFrame,
    fee_per_trade: float,
    slippage_points: float,
) -> dict:
    if future.empty or plan.entry is None or plan.stop_loss is None or plan.target is None:
        return {"outcome": "open", "bars_held": 0, "r_multiple": 0.0, "exit_price": None}

    risk = abs(plan.entry - plan.stop_loss)
    if risk <= 0:
        return {"outcome": "open", "bars_held": 0, "r_multiple": 0.0, "exit_price": None}

    for bars_held, candle in enumerate(future.itertuples(index=False), start=1):
        if plan.bias == "BULLISH":
            stop_hit = float(candle.low) <= plan.stop_loss
            target_hit = float(candle.high) >= plan.target
            if stop_hit:
                exit_price = plan.stop_loss - slippage_points
                return _outcome("stop", bars_held, plan.entry, exit_price, risk, plan.bias, fee_per_trade)
            if target_hit:
                exit_price = plan.target - slippage_points
                return _outcome("target", bars_held, plan.entry, exit_price, risk, plan.bias, fee_per_trade)
        else:
            stop_hit = float(candle.high) >= plan.stop_loss
            target_hit = float(candle.low) <= plan.target
            if stop_hit:
                exit_price = plan.stop_loss + slippage_points
                return _outcome("stop", bars_held, plan.entry, exit_price, risk, plan.bias, fee_per_trade)
            if target_hit:
                exit_price = plan.target + slippage_points
                return _outcome("target", bars_held, plan.entry, exit_price, risk, plan.bias, fee_per_trade)

    last_close = float(future.iloc[-1]["close"])
    return _outcome("timeout", len(future), plan.entry, last_close, risk, plan.bias, fee_per_trade)


def _filter_date_range(
    df: pd.DataFrame,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
) -> pd.DataFrame:
    if df.empty or "timestamp" not in df:
        return df
    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    if start is not None:
        work = work[work["timestamp"] >= pd.Timestamp(start)]
    if end is not None:
        work = work[work["timestamp"] <= pd.Timestamp(end)]
    return work.reset_index(drop=True)


def _outcome(
    outcome: str,
    bars_held: int,
    entry: float,
    exit_price: float,
    risk: float,
    bias: str,
    fee_per_trade: float,
) -> dict:
    gross = exit_price - entry if bias == "BULLISH" else entry - exit_price
    r_multiple = (gross - fee_per_trade) / risk
    return {
        "outcome": outcome,
        "bars_held": bars_held,
        "r_multiple": round(r_multiple, 3),
        "exit_price": round(exit_price, 2),
    }
