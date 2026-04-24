from __future__ import annotations


SETUP_LABELS = {
    "BUY_BREAKOUT": "Potential bullish breakout scenario",
    "BUY_PULLBACK": "Potential bullish pullback scenario",
    "SELL_BREAKDOWN": "Potential bearish breakdown scenario",
    "SELL_RETEST": "Potential bearish retest scenario",
    "WAIT": "No actionable setup",
    "SKIP": "Setup skipped by risk filter",
    "NONE": "No setup",
}

SIGNAL_LABELS = {
    "BUY BREAKOUT": "Bullish breakout watch",
    "SELL BREAKDOWN": "Bearish breakdown watch",
    "FAKE BREAKOUT": "Possible failed bullish breakout",
    "FAKE BREAKDOWN": "Possible failed bearish breakdown",
    "BULLISH BIAS": "Bullish bias",
    "BEARISH BIAS": "Bearish bias",
    "WAIT FOR PULLBACK": "Wait for bullish pullback",
    "WAIT FOR RETEST": "Wait for bearish retest",
    "WAIT": "Wait",
}


def setup_label(setup: str) -> str:
    return SETUP_LABELS.get(setup, setup.replace("_", " ").title())


def signal_label(signal: str) -> str:
    return SIGNAL_LABELS.get(signal, signal.replace("_", " ").title())
