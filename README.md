# OMX Intraday Analysis Dashboard

A Streamlit dashboard for intraday market analysis. It downloads recent intraday candles with `yfinance`, plots price action with EMA20 and detected support/resistance levels, classifies the current market structure, and builds a simple risk-managed trade plan.

The app is intended for learning, experimentation, and workflow support. It is not financial advice.

## What The App Shows

The dashboard has three main areas:

| Area | Purpose |
| --- | --- |
| Sidebar controls | Choose symbol, interval, refresh speed, portfolio size, risk %, presets, and debug mode. |
| Candlestick chart | Displays intraday price candles, EMA20, detected supports, and detected resistances. |
| Market Read + Trade Engine | Summarizes market structure, levels, signal, reasoning, entry, stop, target, R/R, and position size. |

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
6. Use `Quick presets` to quickly switch to common symbols.
7. Enable `Show debug errors` only when troubleshooting.

The right panel gives a plain-language interpretation:

| Field | Meaning |
| --- | --- |
| `Structure` | Current market regime, such as `breakout`, `breakdown`, `uptrend`, `downtrend`, or `range`. |
| `Supports` | Price zones where recent local lows clustered. |
| `Resistances` | Price zones where recent local highs clustered. |
| `Signal` | A higher-level read, such as bearish bias, bullish bias, breakout, breakdown, fake breakout, or wait. |
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
├── analysis/
│   ├── levels.py
│   ├── market_structure.py
│   ├── signals.py
│   ├── structure.py
│   └── trade_engine.py
├── charts/
│   └── plotly_chart.py
├── data/
│   ├── provider_base.py
│   ├── provider_yfinance.py
│   └── models.py
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

### `data/provider_yfinance.py`

`YFinanceProvider` downloads intraday data and normalizes it into a consistent DataFrame shape:

```text
timestamp, open, high, low, close, volume
```

This keeps the rest of the app independent from the exact column names returned by `yfinance`.

### `analysis/levels.py`

`find_levels()` detects support and resistance by:

1. Looking at recent candles only.
2. Finding local highs and local lows.
3. Clustering nearby highs/lows into levels.
4. Keeping only clusters with enough touches.
5. Rounding the final levels for display.

When `tolerance=None`, the function uses an adaptive tolerance based on recent price and candle ranges. That makes the level detection more portable across instruments with very different price scales.

### `analysis/market_structure.py`

`classify_structure()` provides a regime label. It looks at recent candles, EMA20, highs, lows, slope, and range size to classify states such as:

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

This label is later used by both the signal classifier and trade engine.

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

### `charts/plotly_chart.py`

`build_candlestick_chart()` creates the Plotly chart. It renders:

- Candlesticks.
- EMA20 line.
- Support lines.
- Resistance lines.

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

## Interpreting The Trade Engine

The trade engine is deliberately conservative. It separates market bias from actionable setup.

Examples:

| Output | Interpretation |
| --- | --- |
| `Bias: BULLISH` | Conditions favor upside setups. |
| `Bias: BEARISH` | Conditions favor downside setups. |
| `Setup: WAIT` | There is no clean setup yet. |
| `Setup: SKIP` | There was a candidate setup, but it failed a filter such as R/R. |
| `Setup: BUY_BREAKOUT` | Price freshly broke above resistance. |
| `Setup: SELL_BREAKDOWN` | Price freshly broke below support. |

A trade plan should be read as a scenario, not an instruction. The app does not place orders.

## Potential Improvement

The strongest next improvement would be a small backtesting and replay module.

Right now, the dashboard tells you what the rules say at the latest candle. A backtest/replay layer would answer the more important question: how have these rules behaved historically?

A useful first version could:

- Store downloaded intraday candles locally in `data/cache/`.
- Replay candles one by one through `find_levels()`, `classify_structure()`, `classify_signal()`, and `build_trade_plan()`.
- Record every generated setup with entry, stop, target, R/R, and outcome.
- Show win rate, average R/R, max drawdown, number of trades, and performance by symbol/interval.
- Add a Streamlit page called `Backtest` with controls for symbol, interval, date range, portfolio size, and risk percent.

This would turn the app from a live scanner into a strategy research tool. It would also make it much easier to tune thresholds such as EMA span, level tolerance, minimum touches, and minimum R/R with evidence instead of intuition.

## Smaller Future Ideas

- Add market-hours awareness so OMX, US stocks, crypto, and FX are handled differently.
- Add timezone formatting for the last candle timestamp.
- Add alerting when a fresh breakout/breakdown appears.
- Add an option to hide old support/resistance levels that are far from price.
- Add multiple moving averages, VWAP, or ATR bands.
- Add broker fee/slippage assumptions to position sizing.
- Add a watchlist mode that scans several symbols at once.

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

