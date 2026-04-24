from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketSession:
    name: str
    timezone: str
    opens_at: str
    closes_at: str
    is_24_7: bool = False


MARKET_SESSIONS = {
    "OMX": MarketSession("OMX Stockholm", "Europe/Stockholm", "09:00", "17:30"),
    "US": MarketSession("US regular session", "America/New_York", "09:30", "16:00"),
    "FX": MarketSession("FX", "UTC", "00:00", "23:59"),
    "CRYPTO": MarketSession("Crypto", "UTC", "00:00", "23:59", is_24_7=True),
}


def infer_market(symbol: str) -> str:
    upper = symbol.upper()
    if upper.endswith("-USD") or upper in {"BTC", "ETH"}:
        return "CRYPTO"
    if upper.endswith("=X"):
        return "FX"
    if upper.startswith("^OMX") or upper.endswith(".ST"):
        return "OMX"
    return "US"


def get_market_session(symbol: str) -> MarketSession:
    return MARKET_SESSIONS[infer_market(symbol)]


def format_timestamp(
    timestamp: pd.Timestamp,
    timezone: str = "Europe/Stockholm",
) -> str:
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S %Z")


def market_status(
    symbol: str,
    now: pd.Timestamp | None = None,
) -> str:
    session = get_market_session(symbol)
    if session.is_24_7:
        return f"{session.name}: open 24/7"

    current = pd.Timestamp.now(tz=session.timezone) if now is None else pd.Timestamp(now)
    if current.tzinfo is None:
        current = current.tz_localize(session.timezone)
    current = current.tz_convert(session.timezone)

    if current.weekday() >= 5 and session.name != "FX":
        return f"{session.name}: closed for weekend"

    open_time = pd.Timestamp(f"{current.date()} {session.opens_at}", tz=session.timezone)
    close_time = pd.Timestamp(f"{current.date()} {session.closes_at}", tz=session.timezone)

    if open_time <= current <= close_time:
        return f"{session.name}: open until {session.closes_at} {current.tzname()}"
    return f"{session.name}: closed; regular hours {session.opens_at}-{session.closes_at} {current.tzname()}"
