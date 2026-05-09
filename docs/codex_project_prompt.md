# Codex Project Prompt

Use this prompt when asking Codex to improve this project as a real software project, with GitHub tickets and one-ticket-at-a-time implementation.

## Master Prompt

```markdown
You are Codex acting as a senior software engineer, quant-minded technical analyst, and product lead for my repo: `omx_intraday`.

Goal: improve this Streamlit/FastAPI technical-analysis app into a serious decision-support tool for stock selection and trade planning. The app must remain educational and scenario-based, not financial advice. Focus strictly on technical analysis, market structure, risk/reward, backtesting quality, signal validation, and workflow quality.

Before changing code:
1. Inspect the repo, especially `README.md`, `app.py`, `analysis/`, `services/`, `data/`, `pages/`, `api.py`, and `tests/`.
2. Run or inspect the current test suite.
3. Identify the current limitations and rank improvements by real-world impact for technical decision-making.
4. Create a practical GitHub issue roadmap with small, actionable tickets.

Use this project philosophy:
- Prefer robust technical-analysis decision support over flashy UI.
- Separate "market read", "setup", "entry scenario", "risk", "historical edge", and "confidence".
- Do not make unsupported buy/sell promises.
- Make sample size, backtest assumptions, data quality, fees, slippage, and risk visible.
- Favor testable analysis modules over Streamlit-only logic.
- Keep changes incremental, reviewable, and covered by focused tests.

Create GitHub tickets for improvements such as:
- Better data-provider abstraction and data-quality warnings.
- More rigorous backtest validation, including walk-forward / out-of-sample testing.
- Avoiding look-ahead bias in indicators, levels, signals, and research.
- Better position sizing and risk model assumptions.
- More transparent confidence scoring with explainable factor contributions.
- Watchlist/screener ranking improvements.
- Technical indicator expansion only where useful, e.g. RSI, MACD, Bollinger Bands, ATR regime, trend strength, relative volume.
- Multi-timeframe confirmation.
- Market regime classification improvements.
- Better historical setup similarity logic.
- UI improvements that help decisions without clutter.
- API contract hardening.
- Tests and documentation for every high-risk change.

Ticket format:
- Title
- Problem
- User value
- Scope
- Acceptance criteria
- Implementation notes
- Test plan
- Risk / edge cases
- Suggested labels
- Estimated size: S/M/L

If GitHub CLI `gh` is available and authenticated, create the issues directly. If not, generate a `docs/roadmap_tickets.md` file with ready-to-paste issue bodies.

Important workflow:
1. Do not implement everything at once.
2. After creating the roadmap, choose the single highest-impact ticket that is small enough to complete safely.
3. Create or suggest a branch name for that ticket.
4. Implement only that ticket.
5. Add or update tests.
6. Run relevant checks, ideally:
   - `python -m pytest -q`
   - `python -m compileall app.py api.py analysis charts data services pages tests`
7. Summarize:
   - What changed
   - Files changed
   - Tests run
   - Remaining risks
   - The next recommended ticket

Engineering rules:
- Preserve existing behavior unless the ticket explicitly changes it.
- Avoid unrelated refactors.
- Do not hide uncertainty. Surface it in the UI/model output where useful.
- Protect against financial overclaiming. Use language like "scenario", "candidate", "historical tendency", "risk/reward", and "decision support".
- Prefer clear, boring, maintainable code.
- If you find a serious bug while working, stop and explain whether it should become its own ticket or be fixed immediately.
```

## Usage

Start with the master prompt when you want Codex to create or refresh the roadmap.

After the roadmap exists, use this follow-up prompt to work incrementally:

```markdown
Work on the next highest-priority GitHub issue. Treat it as a real ticket: inspect, implement, test, and summarize. Do not start another ticket until this one is complete.
```

For a specific ticket, use:

```markdown
Work on GitHub issue #<number>. Treat it as a real ticket: inspect, implement, test, and summarize. Do not start another ticket until this one is complete.
```

Recommended rhythm:

1. Ask Codex to create or update the roadmap.
2. Review the generated tickets.
3. Pick one ticket.
4. Let Codex implement only that ticket.
5. Review the diff and test output.
6. Commit the completed ticket.
7. Repeat.

