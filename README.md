# OMX Intraday Analysis Dashboard

A Streamlit dashboard for intraday market analysis. It downloads recent intraday candles with `yfinance`, plots price action with EMA20 and detected support/resistance levels, classifies the current market structure, and builds a simple risk-managed trade plan.

The app is intended for learning, experimentation, and workflow support. It is not financial advice.

## What The App Shows

The dashboard has three main areas:

| Area | Purpose |
| --- | --- |
| Sidebar controls | Choose symbol, interval, refresh speed, portfolio size, risk %, fees, slippage, timezone, overlays, presets, and debug mode. |
| Candlestick chart | Displays intraday price candles, selected EMAs, optional VWAP, optional ATR bands, detected supports, and detected resistances. |
| Market Read + Trade Engine | Shows compact cards for price, signal, confidence, volume context, setup scenario, entry, stop, target, R/R, and position size. |
| Backtest page | Replays the rules candle by candle and reports win rate, total R, drawdown, equity curve, setup stats, and trade history. |
| Historical Research page | Compares the current setup to similar historical setups and shows probability-style output. |
| Watchlist page | Scans multiple symbols and highlights active setups, confidence, volume state, and safer scenario labels. |
| Stock Screener page | Ranks many symbols by current confidence plus historical replay edge. |

Example symbols:

| Market | Symbol examples |
| --- | --- |
| OMX Stockholm 30 index | `^OMX` |
| US stocks | `AAPL`, `MSFT`, `NVDA` |
| ETFs | `SPY` |
| Crypto | `BTC-USD`, `ETH-USD` |
| FX | `EURUSD=X` |

## Quick Start

Create and activate a virtual environment if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

Or, without activating the environment:

```bash
.venv/bin/streamlit run app.py
```

Open the browser URL Streamlit prints, usually:

```text
http://localhost:8501
```

## How To Use The Dashboard

1. Enter a ticker in `Symbol`, for example `^OMX`.
2. Choose an `Interval`, such as `1m`, `2m`, `5m`, or `15m`.
3. Set `Refresh seconds` to control automatic reload frequency.
4. Set `Portfolio size` to the amount you want the trade engine to size against.
5. Set `Risk per trade (%)` to control maximum risk used in position sizing.
6. Add estimated fees and slippage if you want position sizing and R/R to be more conservative.
7. Pick a display timezone for the last candle timestamp.
8. Pick an optional confirmation timeframe to compare the current setup with a broader trend.
9. Choose chart overlays such as extra EMAs, VWAP, and ATR bands.
10. Toggle `Show indicator context` to show or hide the RSI/MACD/Bollinger summary.
11. Use `Show levels within % of price` to hide distant support/resistance lines.
12. Use `Clean chart mode` when the chart gets too busy.
13. Use `Quick presets` to quickly switch to common symbols.
14. Save your preferred settings with `Save current settings`.
15. Enable `Show debug errors` only when troubleshooting.

The right panel gives a plain-language interpretation:

| Field | Meaning |
| --- | --- |
| `Structure` | Current market regime, such as `breakout`, `breakdown`, `uptrend`, `downtrend`, or `range`. |
| `Regime context` | Explainable bias, trend, range, breakout state, EMA distance, and EMA slope behind the structure label. |
| `Supports` | Price zones where recent local lows clustered. |
| `Resistances` | Price zones where recent local highs clustered. |
| `Signal` | A higher-level read, such as bearish bias, bullish bias, breakout, breakdown, fake breakout, or wait. |
| `Confidence` | A 0-100 score built from trend alignment, level location, R/R, volume, freshness, and optional higher-timeframe confirmation. |
| `Volume context` | Latest volume compared with recent average volume. |
| `Volatility context` | Current ATR compared with recent ATR history, labeled as quiet, normal, elevated, or extreme. |
| `Indicator context` | RSI, MACD, Bollinger position, and EMA20 slope summarized as supporting context, not standalone signals. |
| `Trade Engine` | A possible plan if conditions meet the strategy rules. |
| `R/R ratio` | Reward-to-risk ratio based on entry, stop, and target. |
| `Position size` | Shares/contracts based on portfolio size, risk %, entry, and stop. |

## Important Limitations

- `yfinance` intraday data can be delayed, incomplete, throttled, or unavailable for some tickers.
- Signals are rule-based and do not know about news, macro events, liquidity, spreads, fees, or order-book depth.
- Position sizing assumes the displayed instrument can be traded in whole units and does not account for broker-specific rules.
- Index symbols such as `^OMX` may not be directly tradable as shares. Treat plans for indexes as analytical reference unless mapped to a tradable product.
- The app is educational analysis only and should not be used as the sole basis for real trades.

## Code Design

The code is intentionally split into small modules so the dashboard stays readable and the analysis logic can be tested separately.

```text
.
├── app.py
├── api.py
├── analysis/
│   ├── backtest.py
│   ├── confidence.py
│   ├── indicators.py
│   ├── levels.py
│   ├── market_hours.py
│   ├── market_structure.py
│   ├── research.py
│   ├── signals.py
│   ├── structure.py
│   ├── trade_engine.py
│   └── volume.py
├── charts/
│   └── plotly_chart.py
├── config/
│   └── settings.py
├── data/
│   ├── provider_base.py
│   ├── provider_yfinance.py
│   └── models.py
├── pages/
│   ├── 1_Backtest.py
│   ├── 2_Watchlist.py
│   ├── 3_Historical_Research.py
│   └── 4_Stock_Screener.py
├── services/
│   └── market_analysis.py
├── ui/
│   └── labels.py
├── tests/
│   └── test_analysis.py
└── requirements.txt
```

### `app.py`

`app.py` is the Streamlit orchestration layer. It is responsible for:

- Configuring the page.
- Reading sidebar inputs.
- Refreshing the app on a timer.
- Fetching data through `YFinanceProvider`.
- Calling the analysis modules in order.
- Rendering the chart and right-side summary panel.
- Showing market-hours context and timezone-formatted candle timestamps.
- Showing confidence and volume context.
- Saving preferred user settings locally.
- Sending setup alerts in the UI when a fresh actionable setup appears.
- Showing optional debug details when something fails.

The main pipeline is:

```text
sidebar inputs
  -> YFinanceProvider.get_intraday()
  -> find_levels()
  -> classify_structure()
  -> classify_signal()
  -> build_trade_plan()
  -> build_candlestick_chart()
  -> Streamlit UI
```

### `pages/1_Backtest.py`

The Backtest page replays the current rule set candle by candle. It can use freshly downloaded data or cached local CSV data. It reports:

- Number of generated trades.
- Win rate.
- Total R.
- Max drawdown in R.
- Average R/R.
- Equity curve and drawdown chart.
- Per-setup statistics.
- Optional date filtering.
- Optional overlapping-trade prevention.
- Small parameter scan across warmup and max-hold values.
- Full trade table.
- Downloadable trade CSV.

### `pages/2_Watchlist.py`

The Watchlist page scans several symbols with the same market-read and trade-engine pipeline. It separates active setups from the full scan table so potential opportunities are easier to spot. It also shows confidence, volume state, relative volume, and safer setup wording.

### `pages/3_Historical_Research.py`

The Historical Research page compares the latest setup with historical replay results. It shows:

- Current confidence score.
- Historical probability based on similar past setups.
- Similar setup sample size.
- Historical win rate and average R.
- A plain-language research decision.
- Equity curve and setup-level results.

### `pages/4_Stock_Screener.py`

The Stock Screener page ranks many symbols by combining:

- Current confidence score.
- Historical probability.
- Total R from replay.
- Drawdown penalty.
- Current setup label.

### `services/market_analysis.py`

The service layer exposes reusable functions for non-Streamlit callers:

- `analyze_dataframe()`
- `analyze_symbol()`
- `research_dataframe()`

This is the bridge toward an API, PWA, or native mobile frontend.

### `api.py`

`api.py` exposes the analysis through FastAPI:

- `GET /health`
- `POST /analyze`
- `POST /research`

Run it with:

```bash
uvicorn api:app --reload
```

### `data/provider_yfinance.py`

`YFinanceProvider` downloads intraday data and normalizes it into a consistent DataFrame shape:

```text
timestamp, open, high, low, close, volume
```

This keeps the rest of the app independent from the exact column names returned by `yfinance`.

Provider failures use typed exceptions from `data/provider_base.py` for common timeout, connection, rate-limit, and schema problems. This lets UI surfaces such as the screener show stable failure categories instead of relying only on raw third-party exception text.

### `analysis/levels.py`

`find_levels()` detects support and resistance by:

1. Looking at recent candles only.
2. Finding local highs and local lows.
3. Clustering nearby highs/lows into levels.
4. Keeping only clusters with enough touches.
5. Rounding the final levels for display.

When `tolerance=None`, the function uses an adaptive tolerance based on recent price and candle ranges. That makes the level detection more portable across instruments with very different price scales.

### `analysis/indicators.py`

`add_indicators()` calculates reusable chart indicators:

- EMA lines.
- VWAP.
- ATR.
- ATR upper/lower bands.
- Optional RSI.
- Optional MACD line, signal line, and histogram.
- Optional Bollinger Bands and percent-B.

`summarize_indicator_context()` turns RSI, MACD, Bollinger position, and EMA20 slope into compact decision-support context. These readings are intentionally exposed as scenario evidence and confidence notes rather than automatic buy/sell signals.

### `analysis/confidence.py`

`score_setup()` creates a 0-100 quality score. It combines:

- Trend/EMA alignment.
- Distance to nearby support or resistance.
- Reward/risk quality.
- Volume confirmation.
- Signal/setup freshness.

The score also returns explainable factor details with each factor's score, maximum score, and reason, while preserving the original numeric component map for API compatibility.

When a confirmation timeframe is supplied, `score_setup()` adds an explainable adjustment for aligned, mixed, unknown, or conflicting higher-timeframe structure. This affects confidence only; it does not change the entry, stop, or target rules.

Volatility regime is added as context in confidence notes when ATR is unusually quiet, elevated, or extreme. It does not change entries, stops, targets, or position sizing.

Indicator context can add notes when RSI is stretched, MACD momentum is directional, or EMA20 slope is strengthening. These notes do not add hidden score points or change the trade plan.

### `analysis/volume.py`

`analyze_volume()` compares the latest candle volume to recent average volume and labels it as `spike`, `above_average`, `normal`, `quiet`, or `unknown`.

### `analysis/market_hours.py`

Market-hours helpers infer whether a symbol is OMX, US, FX, or crypto and format timestamps in the selected display timezone.

### `analysis/market_structure.py`

`analyze_market_regime()` provides an explainable market-regime read with:

- The structure label used by the signal and trade-engine pipeline.
- Directional bias.
- Trend state.
- Range/compression state.
- Breakout state.
- Close location, range %, EMA distance %, and EMA slope %.

`classify_structure()` remains the compatibility wrapper that returns only the structure label. It looks at recent candles, EMA20, highs, lows, slope, and range size to classify states such as:

- `breakout`
- `breakdown`
- `extended_uptrend`
- `extended_downtrend`
- `range_near_highs`
- `range`
- `uptrend`
- `downtrend`
- `bullish_bias`
- `bearish_bias`

This label is later used by both the signal classifier and trade engine. The richer regime context is shown for decision support and API transparency; it does not change entries, stops, targets, or position sizing by itself.

### `analysis/signals.py`

`classify_signal()` converts structure, EMA, supports, and resistances into a readable signal. It can detect:

- Fresh breakout above resistance.
- Fresh breakdown below support.
- Fake breakout.
- Fake breakdown.
- Bullish or bearish bias.
- Wait conditions when no clean trigger exists.

It also returns nearest support and resistance for the right-side UI.

### `analysis/trade_engine.py`

`build_trade_plan()` turns the market read into a possible plan. It calculates:

- Directional bias.
- Setup type, such as `BUY_BREAKOUT`, `BUY_PULLBACK`, `SELL_BREAKDOWN`, or `SELL_RETEST`.
- Entry.
- Stop loss.
- Target.
- Risk per share.
- Reward per share.
- R/R ratio.
- Position size.
- Position value.
- Reason for the plan.

The trade engine only returns active trade ideas when the setup passes a minimum R/R filter. Otherwise it returns `WAIT` or `SKIP` with an explanation.

Position sizing uses:

```text
risk amount = portfolio size * risk percent
risk per share = abs(entry - stop loss)
risk-limited shares = risk amount / risk per share
buying-power shares = portfolio size / entry
position size = min(risk-limited shares, buying-power shares)
```

Fee and slippage settings can reduce the displayed reward and adjust entry/target assumptions.

### `analysis/backtest.py`

`replay_strategy()` walks through candles one at a time and runs the same analysis pipeline used by the live dashboard. `summarize_backtest()` then calculates aggregate results such as win rate, total R, average R/R, and drawdown.

It also includes helpers for equity curves, per-setup summaries, date filtering, overlapping-trade prevention, and a small parameter scan.

### `analysis/research.py`

Research helpers estimate historical edge for the current setup. They convert replay results into probability-style outputs such as:

- Historical probability.
- Similar setup sample size.
- Average R for similar setups.
- Decision labels such as `Watchlist candidate`, `Avoid or wait`, or `Research only`.

### `config/settings.py`

Settings are saved to `config/user_settings.json`, which is ignored by Git. This lets the app remember local preferences without committing personal defaults.

### `ui/labels.py`

UI labels convert raw setup names like `SELL_BREAKDOWN` into safer wording such as `Potential bearish breakdown scenario`.

### `charts/plotly_chart.py`

`build_candlestick_chart()` creates the Plotly chart. It renders:

- Candlesticks.
- Selected EMA lines.
- Optional VWAP.
- Optional ATR bands.
- Support lines.
- Resistance lines.
- Clean chart mode with softer overlays and fewer distractions.

The chart is intentionally kept separate from `app.py` so chart changes do not clutter the app orchestration.

### `tests/test_analysis.py`

The test file covers the most important logic paths:

- Trade engine does not crash when bullish but no support exists.
- Fresh breakout plan generation.
- Fresh breakdown plan generation.
- Position size cap by buying power.
- Adaptive level detection.
- Bullish-bias signal behavior.
- Market-structure classification.
- Indicator generation.
- Cache round trip.
- Market helper formatting.
- Backtest summary behavior.
- Volume analysis.
- Confidence scoring.
- Settings persistence.
- Safer setup labels.
- Backtest equity/setup/optimization helpers.

Run tests with:

```bash
python -m pytest -q
```

Or from the project virtualenv:

```bash
.venv/bin/python -m pytest -q
```

## Development Workflow

Recommended loop:

```bash
source .venv/bin/activate
python -m pytest -q
streamlit run app.py
```

Useful checks:

```bash
python -m compileall app.py analysis charts data tests
python -m pytest -q
```

## Backtesting

Open the Streamlit sidebar navigation and choose `Backtest`.

Backtest replay uses an explicit anti-look-ahead boundary: setup decisions are made from candles up to the decision timestamp, and outcomes are resolved only from later candles. See `docs/backtesting_assumptions.md` for the detailed contract and remaining limitations.

The page can:

- Download latest data and save it to `data/cache/`.
- Reuse cached data for faster repeat runs.
- Filter by optional start/end timestamp.
- Prevent overlapping trades.
- Show equity and drawdown curves.
- Show per-setup statistics.
- Run a small parameter scan.
- Replay entries, stops, targets, fees, and slippage.
- Export the generated trade table as CSV.

Cached CSV files are ignored by Git because they are runtime artifacts.

## Historical Research

Open `Historical Research` in the Streamlit sidebar.

This page is meant for the question: “Has this type of setup worked before?”

It does not predict the future directly. Instead, it compares the current setup with similar historical setups from the replay engine and reports a probability-style estimate. This is safer than a raw buy/sell label because it makes sample size and historical edge visible.

Similarity starts with setup type, then attempts to match context such as structure, trend bias, volume state, R/R bucket, confidence bucket, and market-regime states for trend, range, and breakout context. If strict matching leaves too few samples, research falls back toward setup-only matching and shows what dimensions were actually used.

The page also shows a research-quality panel with matched sample size, replayed trade count, fallback level, matched dimensions, warnings, and out-of-sample validation status. This keeps weak evidence visible instead of hiding it behind a probability-style number.

## Stock Screening

Open `Stock Screener` in the Streamlit sidebar.

Enter one symbol per line. The screener downloads history for each symbol, runs the current read plus historical research, and ranks the results. This is useful for finding candidates worth deeper review.

Screener rows include research quality, fallback level, validation status, matched dimensions, and quality warnings. Results are split into ranking, quality, research-detail, and all-column tabs so the table stays easier to scan. Individual symbol failures are isolated into failed rows with status reasons so one bad ticker does not stop the whole scan; common provider timeouts, connection errors, rate limits, schema mismatches, and no-data cases are categorized for easier review. A symbol must pass probability, positive-total-R, and usable-quality filters before appearing as a higher-quality candidate.

## API And Mobile Path

The app now has a FastAPI-compatible service boundary.

Start the API:

```bash
uvicorn api:app --reload
```

Example request:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","interval":"15m","period":"1mo"}'
```

API requests validate supported intervals, periods, portfolio/risk bounds, fees, slippage, warmup, hold bars, and train/test split fraction before running analysis. Invalid requests return FastAPI validation errors instead of reaching the market-data provider.

Recommended Android path:

1. Keep the analysis engine in Python.
2. Host `api.py` on a server or home machine.
3. Build a mobile-friendly PWA or Android app that calls `/analyze` and `/research`.
4. Add authentication before exposing the API publicly.

Fastest installable Android experience:

1. Host the Streamlit app or a future PWA.
2. Open it in Chrome on Android.
3. Use `Add to Home screen`.

Native Android is possible later, but the current service layer makes a PWA or API-backed mobile frontend the lower-risk next step.

## Watchlist Scanning

Open the Streamlit sidebar navigation and choose `Watchlist`.

Enter one symbol per line, for example:

```text
^OMX
AAPL
MSFT
NVDA
SPY
BTC-USD
EURUSD=X
```

The scanner shows active setups separately from the full watchlist table. It also includes confidence, volume state, relative volume, safer signal/setup labels, and saved watchlist support.

## Interpreting The Trade Engine

The trade engine is deliberately conservative. It separates market bias from actionable setup.

Examples:

| Output | Interpretation |
| --- | --- |
| `Bias: BULLISH` | Conditions favor upside setups. |
| `Bias: BEARISH` | Conditions favor downside setups. |
| `Setup: WAIT` | There is no clean setup yet. |
| `Setup: SKIP` | There was a candidate setup, but it failed a filter such as R/R. |
| `Potential bullish breakout scenario` | Price freshly broke above resistance. |
| `Potential bearish breakdown scenario` | Price freshly broke below support. |

A trade plan should be read as a scenario, not an instruction. The app does not place orders.

## Implemented Improvements

- Backtesting and replay page.
- Historical research page with probability-style output.
- Local data caching in `data/cache/`.
- Watchlist scanner.
- Stock screener with historical edge ranking.
- FastAPI service boundary for future mobile/PWA clients.
- Market-hours awareness for OMX, US, FX, and crypto.
- Timezone-formatted timestamps.
- Setup alerts in the live dashboard.
- Optional filtering for distant support/resistance levels.
- Multiple EMAs, VWAP, and ATR bands.
- Fee and slippage assumptions in trade planning.
- Compact card-based Market Read panel.
- Clean chart mode and softer chart overlays.
- Strategy confidence score.
- Volume analysis.
- ATR-based volatility regime context.
- RSI, MACD, Bollinger, and EMA20-slope indicator context.
- Explainable market-regime context behind the structure label.
- Saved user settings and watchlist.
- Backtest equity curve, per-setup stats, date filtering, overlap prevention, and parameter scan.

## Potential Next Improvement

The strongest next improvement is a richer data layer. `yfinance` is good for prototyping, but a serious research tool would benefit from a dedicated market-data provider with deeper intraday history, adjusted corporate actions, cleaner volume, fundamentals, and survivorship-bias-aware universes.

## Terminal Helper Appendix

This repository also has a README history around Bash helpers in `/home/en23/.bash_aliases`. Reload aliases with:

```bash
source ~/.bash_aliases
```

Common shortcuts from that file:

| Task | Command |
| --- | --- |
| Show Git status | `gs` |
| Show Git diff | `gd` |
| Show staged diff | `gds` |
| Show recent Git history | `gl` |
| Create and enter a folder | `mkcd folder-name` |
| Move up two directories | `up 2` |
| Fuzzy-find a directory | `fcd` |
| Fuzzy-open a file | `fopen` |
| Search and open a result | `frg "text"` |
| Show readable `PATH` | `path` |
