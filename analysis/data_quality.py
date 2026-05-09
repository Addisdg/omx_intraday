from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
OHLC_COLUMNS = ["open", "high", "low", "close"]


def assess_data_quality(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "status": "no_data",
            "summary": "No candle data available",
            "row_count": 0,
            "first_timestamp": None,
            "last_timestamp": None,
            "issues": ["No candle data was returned"],
        }

    issues: list[str] = []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        return {
            "status": "invalid",
            "summary": "Data is missing required candle columns",
            "row_count": int(len(df)),
            "first_timestamp": None,
            "last_timestamp": None,
            "issues": [f"Missing required columns: {', '.join(missing_columns)}"],
        }

    timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
    invalid_timestamp_count = int(timestamps.isna().sum())
    if invalid_timestamp_count:
        issues.append(f"{invalid_timestamp_count} candle(s) have invalid timestamps")

    valid_timestamps = timestamps.dropna()
    if not valid_timestamps.empty:
        duplicate_timestamp_count = int(valid_timestamps.duplicated().sum())
        if duplicate_timestamp_count:
            issues.append(f"{duplicate_timestamp_count} duplicate timestamp(s) detected")

        if not valid_timestamps.is_monotonic_increasing:
            issues.append("Timestamps are not sorted in ascending order")

    numeric = df[OHLC_COLUMNS + ["volume"]].apply(pd.to_numeric, errors="coerce")
    missing_ohlc_count = int(numeric[OHLC_COLUMNS].isna().sum().sum())
    if missing_ohlc_count:
        issues.append(f"{missing_ohlc_count} missing or non-numeric OHLC value(s) detected")

    invalid_ohlc_rows = _invalid_ohlc_rows(numeric)
    if invalid_ohlc_rows:
        issues.append(f"{invalid_ohlc_rows} candle(s) have inconsistent OHLC relationships")

    missing_volume_count = int(numeric["volume"].isna().sum())
    if missing_volume_count:
        issues.append(f"{missing_volume_count} missing or non-numeric volume value(s) detected")

    zero_or_missing_volume_ratio = float((numeric["volume"].fillna(0) <= 0).mean())
    if len(df) >= 5 and zero_or_missing_volume_ratio >= 0.8:
        issues.append("Volume is mostly zero or missing; volume-based confirmation may be unreliable")

    status = "warning" if issues else "ok"
    return {
        "status": status,
        "summary": "Data quality checks passed" if status == "ok" else "Data quality warnings detected",
        "row_count": int(len(df)),
        "first_timestamp": _timestamp_text(valid_timestamps.iloc[0]) if not valid_timestamps.empty else None,
        "last_timestamp": _timestamp_text(valid_timestamps.iloc[-1]) if not valid_timestamps.empty else None,
        "issues": issues,
    }


def _invalid_ohlc_rows(numeric: pd.DataFrame) -> int:
    complete = numeric[OHLC_COLUMNS].dropna()
    if complete.empty:
        return 0

    invalid = (
        (complete["high"] < complete["low"])
        | (complete["open"] > complete["high"])
        | (complete["open"] < complete["low"])
        | (complete["close"] > complete["high"])
        | (complete["close"] < complete["low"])
    )
    return int(invalid.sum())


def _timestamp_text(value: pd.Timestamp) -> str:
    return value.isoformat()

