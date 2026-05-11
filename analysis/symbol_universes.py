from __future__ import annotations

import re


SYMBOL_UNIVERSES = {
    "Default Demo": [
        "AAPL",
        "MSFT",
        "NVDA",
        "SPY",
        "BTC-USD",
        "ETH-USD",
        "EURUSD=X",
    ],
    "US Large/Liquid Stocks": [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "GOOG",
        "META",
        "TSLA",
        "AVGO",
        "BRK-B",
        "LLY",
        "JPM",
        "V",
        "UNH",
        "XOM",
        "MA",
        "COST",
        "HD",
        "PG",
        "NFLX",
        "JNJ",
        "ABBV",
        "BAC",
        "KO",
        "CRM",
        "ORCL",
        "AMD",
        "MRK",
        "CVX",
        "WMT",
        "PEP",
        "ADBE",
        "CSCO",
        "MCD",
        "TMO",
        "ACN",
        "ABT",
        "LIN",
        "GE",
        "DIS",
        "IBM",
        "QCOM",
        "INTU",
        "AMAT",
        "NOW",
        "TXN",
        "CAT",
        "VZ",
        "ISRG",
        "AMGN",
        "CMCSA",
        "NEE",
        "PM",
        "RTX",
        "SPGI",
        "LOW",
        "HON",
        "UBER",
        "BKNG",
        "PFE",
        "COP",
        "GS",
        "TJX",
        "BA",
        "SYK",
        "DE",
        "MS",
        "PLD",
        "BLK",
        "ADP",
        "MDLZ",
        "SBUX",
        "GILD",
        "LRCX",
        "REGN",
        "ADI",
        "PANW",
        "MU",
        "C",
        "CVS",
        "MMC",
        "ELV",
        "SCHW",
        "ETN",
        "SO",
        "ANET",
        "KLAC",
        "CB",
    ],
    "US Growth / Momentum": [
        "NVDA",
        "TSLA",
        "AMD",
        "META",
        "NFLX",
        "AVGO",
        "SMCI",
        "ARM",
        "PLTR",
        "CRWD",
        "NET",
        "DDOG",
        "SNOW",
        "SHOP",
        "MELI",
        "COIN",
        "HOOD",
        "APP",
        "RBLX",
        "ROKU",
        "UBER",
        "ABNB",
        "DASH",
        "PANW",
        "ZS",
        "MDB",
        "TEAM",
        "WDAY",
        "NOW",
        "ADBE",
    ],
    "US Sector ETFs": [
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "VTI",
        "VOO",
        "XLK",
        "XLF",
        "XLE",
        "XLV",
        "XLY",
        "XLI",
        "XLP",
        "XLU",
        "XLB",
        "XLRE",
        "SMH",
        "XBI",
        "ARKK",
        "TLT",
        "GLD",
        "SLV",
        "HYG",
        "LQD",
    ],
    "OMX Stockholm Large/Liquid": [
        "ABB.ST",
        "ALFA.ST",
        "ASSA-B.ST",
        "ATCO-A.ST",
        "ATCO-B.ST",
        "AZN.ST",
        "BOL.ST",
        "ELUX-B.ST",
        "ERIC-B.ST",
        "ESSITY-B.ST",
        "EVO.ST",
        "GETI-B.ST",
        "HM-B.ST",
        "HEXA-B.ST",
        "INVE-B.ST",
        "KINV-B.ST",
        "NDA-SE.ST",
        "SAND.ST",
        "SCA-B.ST",
        "SEB-A.ST",
        "SHB-A.ST",
        "SINCH.ST",
        "SKF-B.ST",
        "SWED-A.ST",
        "TEL2-B.ST",
        "TELIA.ST",
        "VOLV-B.ST",
        "EQT.ST",
        "SAAB-B.ST",
        "NIBE-B.ST",
    ],
    "Nordic Large/Liquid Sample": [
        "NOVO-B.CO",
        "MAERSK-B.CO",
        "CARL-B.CO",
        "DSV.CO",
        "DANSKE.CO",
        "ORSTED.CO",
        "NOKIA.HE",
        "NESTE.HE",
        "KNEBV.HE",
        "SAMPO.HE",
        "EQNR.OL",
        "DNB.OL",
        "MOWI.OL",
        "TEL.OL",
        "NHY.OL",
    ],
    "Crypto / FX": [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "XRP-USD",
        "ADA-USD",
        "EURUSD=X",
        "GBPUSD=X",
        "USDSEK=X",
        "EURSEK=X",
        "USDJPY=X",
    ],
}


def parse_symbol_text(text: str) -> list[str]:
    """Parse pasted symbols from newline, comma, semicolon, or whitespace separated text."""
    symbols = []
    for token in re.split(r"[\s,;]+", text):
        symbol = token.strip().upper()
        if not symbol or symbol.startswith("#") or symbol in {"SYMBOL", "TICKER"}:
            continue
        symbols.append(symbol)
    return dedupe_symbols(symbols)


def dedupe_symbols(symbols: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        deduped.append(symbol)
    return deduped


def build_screening_universe(
    selected_universes: list[str],
    manual_symbols: str = "",
    uploaded_symbols: str = "",
    max_symbols: int = 100,
) -> dict:
    symbols = []
    unknown_universes = []

    for universe in selected_universes:
        if universe not in SYMBOL_UNIVERSES:
            unknown_universes.append(universe)
            continue
        symbols.extend(SYMBOL_UNIVERSES[universe])

    symbols.extend(parse_symbol_text(manual_symbols))
    symbols.extend(parse_symbol_text(uploaded_symbols))
    deduped = dedupe_symbols(symbols)
    capped = deduped[:max_symbols]

    return {
        "symbols": capped,
        "requested_count": len(deduped),
        "selected_count": len(capped),
        "truncated": len(deduped) > len(capped),
        "unknown_universes": unknown_universes,
    }
