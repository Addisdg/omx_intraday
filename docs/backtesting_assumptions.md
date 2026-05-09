# Backtesting Assumptions

The replay engine is designed to reduce look-ahead bias by separating the decision candle from the trade-resolution window.

## Anti-Look-Ahead Contract

For each replay step in `replay_strategy()`:

1. The analysis pipeline receives only candles from the start of the filtered dataset through the current decision candle.
2. Level detection, market-structure classification, and trade-plan generation are run on that historical slice.
3. If an actionable setup is produced, the outcome is resolved only against candles after the decision candle.
4. The trade record includes audit fields:
   - `decision_index`
   - `history_start_timestamp`
   - `history_end_timestamp`
   - `first_resolution_timestamp`

The `timestamp` column on a replayed trade is the decision candle timestamp, not the exit timestamp.

## Important Limits

This does not make a backtest predictive. It only documents and tests the replay-time data boundary.

Backtest results still depend on:

- Data quality and provider limitations.
- Fee and slippage assumptions.
- Intrabar ambiguity when a candle touches both stop and target.
- Parameter choices such as warmup bars and max hold bars.
- Sample size and market regime stability.

Treat replay results as technical research context, not as proof that a setup will work in the future.

