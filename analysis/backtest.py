from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from analysis.confidence import score_setup
from analysis.levels import find_levels
from analysis.market_structure import classify_structure
from analysis.signals import classify_signal
from analysis.timeframes import bias_from_structure
from analysis.trade_engine import TradePlan, build_trade_plan
from analysis.volume import analyze_volume


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
        future_window = df.iloc[idx + 1 : idx + 1 + max_hold_bars]
        levels = find_levels(history, window=3, tolerance=None, min_touches=2)
        structure = classify_structure(history, lookback=min(30, len(history)))
        signal = classify_signal(history, levels["supports"], levels["resistances"], structure)
        volume_read = analyze_volume(history)
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

        confidence = score_setup(
            history,
            structure,
            signal,
            plan,
            levels["supports"],
            levels["resistances"],
            volume_read,
        )
        outcome = _resolve_trade(
            plan=plan,
            future=future_window,
            fee_per_trade=fee_per_trade,
            slippage_points=slippage_points,
        )
        records.append(
            {
                "timestamp": history.iloc[-1]["timestamp"],
                "decision_index": idx,
                "history_start_timestamp": history.iloc[0]["timestamp"],
                "history_end_timestamp": history.iloc[-1]["timestamp"],
                "first_resolution_timestamp": _first_timestamp(future_window),
                "bias": plan.bias,
                "setup": plan.setup,
                "structure": structure,
                "signal": signal["signal"],
                "trend_bias": bias_from_structure(structure),
                "volume_state": volume_read["volume_state"],
                "confidence_score": confidence["score"],
                "confidence_bucket": confidence_bucket(confidence["score"]),
                "rr_bucket": rr_bucket(plan.rr_ratio),
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


def confidence_bucket(score: int | float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80:
        return "high"
    if score >= 60:
        return "moderate"
    if score >= 40:
        return "low"
    return "very_low"


def rr_bucket(rr_ratio: float | None) -> str:
    if rr_ratio is None:
        return "unknown"
    if rr_ratio >= 3:
        return "strong"
    if rr_ratio >= 2:
        return "acceptable"
    if rr_ratio >= 1.5:
        return "marginal"
    return "weak"


def _first_timestamp(df: pd.DataFrame) -> pd.Timestamp | None:
    if df.empty or "timestamp" not in df:
        return None
    return df.iloc[0]["timestamp"]


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


def split_train_test(
    df: pd.DataFrame,
    train_fraction: float = 0.7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    if df.empty:
        return df.copy(), df.copy()

    split_index = max(1, min(len(df) - 1, int(len(df) * train_fraction)))
    train = df.iloc[:split_index].reset_index(drop=True)
    test = df.iloc[split_index:].reset_index(drop=True)
    return train, test


def validate_out_of_sample(
    df: pd.DataFrame,
    portfolio_size_sek: float = 30_000,
    risk_percent: float = 1.0,
    warmup: int = 30,
    max_hold_bars: int = 30,
    train_fraction: float = 0.7,
    fee_per_trade: float = 0.0,
    slippage_points: float = 0.0,
    prevent_overlaps: bool = True,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> dict:
    filtered = _filter_date_range(df, start, end)
    train_df, test_df = split_train_test(filtered, train_fraction=train_fraction)

    in_sample_trades = replay_strategy(
        df=train_df,
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        warmup=warmup,
        max_hold_bars=max_hold_bars,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
        prevent_overlaps=prevent_overlaps,
    )
    out_of_sample_trades = replay_strategy(
        df=test_df,
        portfolio_size_sek=portfolio_size_sek,
        risk_percent=risk_percent,
        warmup=warmup,
        max_hold_bars=max_hold_bars,
        fee_per_trade=fee_per_trade,
        slippage_points=slippage_points,
        prevent_overlaps=prevent_overlaps,
    )
    in_sample_summary = summarize_backtest(in_sample_trades)
    out_of_sample_summary = summarize_backtest(out_of_sample_trades)

    return {
        "train_fraction": train_fraction,
        "split_index": len(train_df),
        "split_timestamp": _first_timestamp(test_df),
        "in_sample_rows": len(train_df),
        "out_of_sample_rows": len(test_df),
        "in_sample_summary": in_sample_summary,
        "out_of_sample_summary": out_of_sample_summary,
        "verdict": _out_of_sample_verdict(
            in_sample_summary=in_sample_summary,
            out_of_sample_summary=out_of_sample_summary,
            out_of_sample_rows=len(test_df),
            warmup=warmup,
        ),
    }


def _out_of_sample_verdict(
    in_sample_summary: BacktestSummary,
    out_of_sample_summary: BacktestSummary,
    out_of_sample_rows: int,
    warmup: int,
) -> str:
    if out_of_sample_rows <= warmup:
        return "Not enough out-of-sample candles after the split"
    if out_of_sample_summary.trades == 0:
        return "No out-of-sample setups were generated"
    if in_sample_summary.total_r > 0 and out_of_sample_summary.total_r > 0:
        return "Out-of-sample validation supports the in-sample result"
    if in_sample_summary.total_r > 0 and out_of_sample_summary.total_r <= 0:
        return "In-sample edge did not hold out of sample"
    if out_of_sample_summary.total_r > 0:
        return "Out-of-sample result is positive, but in-sample edge was weak"
    return "No positive out-of-sample validation detected"


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
