# OMX Intraday Roadmap Tickets

GitHub CLI `gh` was not available in this environment, so these are ready-to-paste GitHub issue bodies.

## 1. Add Candle Data Quality Diagnostics

Problem:
The app depends on intraday OHLCV candles from `yfinance`, but the current analysis pipeline mostly treats every non-empty DataFrame as equally trustworthy.

User value:
Technical-analysis decisions become safer when stale, sparse, malformed, duplicated, zero-volume, or non-monotonic data is visible before interpreting signals.

Scope:
Add a reusable data-quality assessment module and expose its output in the service/API and main dashboard.

Acceptance criteria:
- A reusable function reports row count, timestamp range, status, and issue list.
- It detects empty data, missing required columns, duplicate timestamps, non-monotonic timestamps, invalid OHLC relationships, missing OHLC values, and suspicious volume.
- `analyze_dataframe()` includes data-quality output.
- The main dashboard shows a concise data-quality status.
- Tests cover good data and multiple warning cases.

Implementation notes:
- Keep this separate from `YFinanceProvider` so cached data and future providers can use it.
- Do not block analysis for warnings; surface uncertainty unless data is unusable.

Test plan:
- Add focused unit tests in `tests/test_analysis.py`.
- Run `python -m pytest -q`.
- Run `python -m compileall app.py api.py analysis charts data services pages tests`.

Risk / edge cases:
- Some valid instruments have zero or sparse volume.
- Crypto/FX volume can be provider-specific.

Suggested labels:
`enhancement`, `data-quality`, `technical-analysis`, `small`

Estimated size:
S

## 2. Add Look-Ahead Bias Audit Helpers For Backtests

Problem:
The replay engine uses historical slices, but there is no explicit audit output proving each indicator, level, signal, and setup only uses candles available at that replay point.

User value:
Backtest results become more trustworthy and easier to reason about before using them in a decision workflow.

Scope:
Add explicit tests and optional debug metadata around replay-time data slicing.

Acceptance criteria:
- Tests assert backtest decisions are made only from candles up to the current replay index.
- Replay output can include the decision timestamp and first future candle used for resolution.
- Documentation explains the anti-look-ahead assumption.

Implementation notes:
- Keep behavior unchanged unless a bug is found.
- Prefer small tests around `replay_strategy()`.

Test plan:
- Add regression tests with synthetic candles designed to fail if future data leaks.
- Run full tests.

Risk / edge cases:
- Some existing level detection behavior may need careful interpretation because local extrema require surrounding candles inside the already-known history.

Suggested labels:
`backtest`, `correctness`, `risk-control`, `medium`

Estimated size:
M

## 3. Add Walk-Forward / Out-Of-Sample Backtest Validation

Problem:
The current backtest summarizes a single replay over the selected history, which can overstate confidence if parameters are tuned on the same data.

User value:
The app can distinguish researched setups from overfit setups.

Scope:
Add train/test date split support and walk-forward summary output.

Acceptance criteria:
- Backtest page supports an out-of-sample split.
- Summary separates in-sample and out-of-sample performance.
- Research output reports whether historical edge survives the split.
- Tests cover split behavior.

Implementation notes:
- Start with one simple chronological split before adding rolling windows.

Test plan:
- Unit tests for split helper.
- Backtest summary tests.

Risk / edge cases:
- Very small intraday datasets may not have enough samples after splitting.

Suggested labels:
`backtest`, `research`, `medium`

Estimated size:
M

## 4. Make Confidence Scoring Explainable

Problem:
The confidence score has components, but the output does not fully explain why each component received its score.

User value:
The user can understand whether confidence comes from trend, levels, volume, freshness, or R/R instead of treating the score as a black box.

Scope:
Return structured factor explanations and expose them in the dashboard/API.

Acceptance criteria:
- Each confidence component includes score, max score, and reason.
- Existing numeric component output remains available or is migrated safely.
- UI shows concise factor explanations.
- Tests cover factor reasons.

Implementation notes:
- Consider preserving `components` for compatibility and adding `factors`.

Test plan:
- Unit tests for high/low R/R, volume states, and no-actionable-setup cap.

Risk / edge cases:
- API consumers may rely on the current `components` shape.

Suggested labels:
`confidence`, `explainability`, `api`, `small`

Estimated size:
S

## 5. Add Multi-Timeframe Confirmation

Problem:
Signals are generated from one interval at a time, which can create noisy intraday setups against a higher-timeframe trend.

User value:
Candidate setups can be filtered or annotated by broader trend alignment.

Scope:
Fetch and analyze a configurable higher timeframe and include confirmation in confidence and UI.

Acceptance criteria:
- User can choose a confirmation timeframe.
- Output shows aligned, mixed, or conflicting trend context.
- Confidence scoring can add or subtract based on confirmation.
- Tests cover the timeframe-comparison logic without network calls.

Implementation notes:
- Keep fetching separate from comparison logic.

Test plan:
- Unit tests with synthetic lower/higher timeframe DataFrames.

Risk / edge cases:
- Provider limits may make multiple downloads slower or unavailable.

Suggested labels:
`technical-analysis`, `multi-timeframe`, `medium`

Estimated size:
M

## 6. Improve Historical Setup Similarity

Problem:
Historical research currently compares mostly by setup label, which may group together setups with different regime, volume, R/R, and level context.

User value:
Probability-style output becomes more relevant to the current market condition.

Scope:
Add similarity dimensions such as setup, structure, confidence bucket, volume state, R/R bucket, and trend regime.

Acceptance criteria:
- Replay records store enough setup context for similarity filtering.
- Research output reports matched dimensions and sample size.
- Low sample size is clearly surfaced.
- Tests cover fallback behavior when strict matching has too few samples.

Implementation notes:
- Start with simple buckets, not machine learning.

Test plan:
- Synthetic replay/trades tests.

Risk / edge cases:
- More filters can reduce sample size too aggressively.

Suggested labels:
`research`, `historical-edge`, `medium`

Estimated size:
M

## 7. Harden API Request Validation And Response Contracts

Problem:
The FastAPI models accept broad numeric/string inputs and return dataclasses converted through a generic helper.

User value:
API-backed frontends and future mobile/PWA clients get clearer errors and stable response shapes.

Scope:
Add request bounds, allowed intervals, response-friendly data models, and tests.

Acceptance criteria:
- Invalid intervals and risk settings return validation errors.
- Trade plan and research outputs serialize predictably.
- Tests cover `/health`, `/analyze`, and `/research` model behavior.

Implementation notes:
- Avoid live network calls in API tests by testing model validation or monkeypatching providers.

Test plan:
- Unit tests for request model validation and `_json_safe()`.

Risk / edge cases:
- Pydantic version differences may affect validation syntax.

Suggested labels:
`api`, `validation`, `small`

Estimated size:
S

## 8. Add ATR/Volatility Regime Context To Trade Plans

Problem:
The trade engine uses ATR-like ranges for stops but does not expose whether current volatility is quiet, normal, elevated, or extreme.

User value:
The user can avoid over-trusting setups during abnormal volatility or recognize when wider stops are caused by the market environment.

Scope:
Add a volatility regime helper and include it in confidence notes and UI.

Acceptance criteria:
- A reusable helper classifies current ATR versus recent ATR history.
- Dashboard/API expose the volatility regime.
- Tests cover quiet, normal, elevated, and insufficient-data states.

Implementation notes:
- Keep this as context first; do not change entries/stops until separately ticketed.

Test plan:
- Unit tests with synthetic candles.

Risk / edge cases:
- Short intraday datasets may make regime classification noisy.

Suggested labels:
`technical-analysis`, `risk`, `small`

Estimated size:
S

## 9. Improve Screener Ranking Transparency

Problem:
The screener rank score combines confidence, probability, total R, and drawdown penalty, but users cannot see factor contributions.

User value:
Stock selection becomes easier to audit and less dependent on a single opaque score.

Scope:
Return ranking components and show them in the screener table.

Acceptance criteria:
- Screener output includes confidence contribution, probability contribution, total-R contribution, and drawdown penalty.
- Candidate filter explains why each candidate passed or failed.
- Tests cover rank-score calculation in a pure helper.

Implementation notes:
- Move rank calculation out of the Streamlit page.

Test plan:
- Unit tests for ranking helper.

Risk / edge cases:
- Existing ranking behavior should remain numerically consistent unless intentionally changed.

Suggested labels:
`screener`, `explainability`, `small`

Estimated size:
S

## 10. Add Technical Indicator Expansion With Guardrails

Problem:
The app has EMA, VWAP, and ATR bands, but common confirmation tools such as RSI, MACD, Bollinger Bands, and trend-strength context are missing.

User value:
The user can evaluate setups with more technical context without replacing the core market-structure workflow.

Scope:
Add a small set of optional, tested indicators and expose only decision-relevant summaries.

Acceptance criteria:
- Indicator calculations are pure and tested.
- UI controls allow enabling optional overlays/summaries.
- Confidence scoring uses new indicators only where justified and documented.

Implementation notes:
- Avoid indicator clutter. Add summaries before overlays where possible.

Test plan:
- Unit tests for each indicator.
- Visual smoke check for chart overlays if added.

Risk / edge cases:
- Too many indicators can create false precision or clutter.

Suggested labels:
`technical-analysis`, `indicators`, `medium`

Estimated size:
M

