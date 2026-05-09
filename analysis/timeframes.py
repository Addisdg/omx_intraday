from __future__ import annotations

import pandas as pd

from analysis.market_structure import classify_structure


BULLISH_STRUCTURES = {"breakout", "uptrend", "bullish_bias", "range_near_highs", "extended_uptrend"}
BEARISH_STRUCTURES = {"breakdown", "downtrend", "bearish_bias", "extended_downtrend"}
NEUTRAL_STRUCTURES = {"range", "insufficient_data"}


def bias_from_structure(structure: str) -> str:
    if structure in BULLISH_STRUCTURES:
        return "BULLISH"
    if structure in BEARISH_STRUCTURES:
        return "BEARISH"
    if structure in NEUTRAL_STRUCTURES:
        return "NEUTRAL"
    return "UNKNOWN"


def compare_timeframes(
    lower_structure: str,
    higher_structure: str,
    higher_interval: str | None = None,
) -> dict:
    lower_bias = bias_from_structure(lower_structure)
    higher_bias = bias_from_structure(higher_structure)
    interval_text = f" on {higher_interval}" if higher_interval else ""

    if higher_bias == "UNKNOWN":
        return {
            "status": "unknown",
            "lower_structure": lower_structure,
            "higher_structure": higher_structure,
            "lower_bias": lower_bias,
            "higher_bias": higher_bias,
            "score_adjustment": 0,
            "reason": f"Higher timeframe{interval_text} could not be classified",
        }

    if lower_bias == "UNKNOWN":
        return {
            "status": "unknown",
            "lower_structure": lower_structure,
            "higher_structure": higher_structure,
            "lower_bias": lower_bias,
            "higher_bias": higher_bias,
            "score_adjustment": 0,
            "reason": "Current timeframe could not be classified",
        }

    if "NEUTRAL" in {lower_bias, higher_bias}:
        return {
            "status": "mixed",
            "lower_structure": lower_structure,
            "higher_structure": higher_structure,
            "lower_bias": lower_bias,
            "higher_bias": higher_bias,
            "score_adjustment": 0,
            "reason": f"Higher timeframe{interval_text} is {higher_bias.lower()}, so confirmation is mixed",
        }

    if lower_bias == higher_bias:
        return {
            "status": "aligned",
            "lower_structure": lower_structure,
            "higher_structure": higher_structure,
            "lower_bias": lower_bias,
            "higher_bias": higher_bias,
            "score_adjustment": 8,
            "reason": f"Higher timeframe{interval_text} confirms the {lower_bias.lower()} structure",
        }

    return {
        "status": "conflicting",
        "lower_structure": lower_structure,
        "higher_structure": higher_structure,
        "lower_bias": lower_bias,
        "higher_bias": higher_bias,
        "score_adjustment": -8,
        "reason": f"Higher timeframe{interval_text} conflicts with the current {lower_bias.lower()} structure",
    }


def build_timeframe_confirmation(
    lower_structure: str,
    higher_df: pd.DataFrame | None,
    higher_interval: str | None = None,
) -> dict:
    if higher_df is None or higher_df.empty:
        return {
            "status": "unknown",
            "lower_structure": lower_structure,
            "higher_structure": "no_data",
            "lower_bias": bias_from_structure(lower_structure),
            "higher_bias": "UNKNOWN",
            "score_adjustment": 0,
            "reason": "No higher-timeframe data was available",
        }

    higher_structure = classify_structure(higher_df, lookback=min(30, len(higher_df)))
    return compare_timeframes(lower_structure, higher_structure, higher_interval=higher_interval)

