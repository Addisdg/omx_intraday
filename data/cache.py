from __future__ import annotations

from pathlib import Path

import pandas as pd


CACHE_DIR = Path("data/cache")


def cache_path(symbol: str, interval: str, cache_dir: Path = CACHE_DIR) -> Path:
    safe_symbol = "".join(ch if ch.isalnum() else "_" for ch in symbol.upper()).strip("_")
    return cache_dir / f"{safe_symbol}_{interval}.csv"


def load_cached_data(
    symbol: str,
    interval: str,
    cache_dir: Path = CACHE_DIR,
) -> pd.DataFrame:
    path = cache_path(symbol, interval, cache_dir)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.dropna(subset=["timestamp"]).reset_index(drop=True)


def save_cached_data(
    df: pd.DataFrame,
    symbol: str,
    interval: str,
    cache_dir: Path = CACHE_DIR,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(symbol, interval, cache_dir)
    work = df.copy()

    if path.exists():
        existing = load_cached_data(symbol, interval, cache_dir)
        work = pd.concat([existing, work], ignore_index=True)

    work = (
        work.drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    work.to_csv(path, index=False)
    return path
