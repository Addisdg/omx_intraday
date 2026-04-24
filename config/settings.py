from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SETTINGS_PATH = Path("config/user_settings.json")

DEFAULT_SETTINGS: dict[str, Any] = {
    "symbol": "^OMX",
    "interval": "1m",
    "refresh_seconds": 10,
    "portfolio_size": 30_000,
    "risk_percent": 1.0,
    "fee_per_trade": 0.0,
    "slippage_points": 0.0,
    "timezone": "Europe/Stockholm",
    "ema_spans": [20],
    "show_vwap": False,
    "show_atr_bands": False,
    "clean_chart_mode": False,
    "level_distance_percent": 0.0,
    "enable_alerts": True,
    "watchlist": "^OMX\nAAPL\nMSFT\nNVDA\nSPY\nBTC-USD\nEURUSD=X",
}


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    if not path.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        loaded = json.loads(path.read_text())
    except json.JSONDecodeError:
        return DEFAULT_SETTINGS.copy()
    return {**DEFAULT_SETTINGS, **loaded}


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, sort_keys=True))
    return path
