from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from data.provider_base import attach_provider_metadata, provider_metadata_from_df


CACHE_DIR = Path("data/cache")


def cache_path(symbol: str, interval: str, cache_dir: Path = CACHE_DIR) -> Path:
    safe_symbol = "".join(ch if ch.isalnum() else "_" for ch in symbol.upper()).strip("_")
    return cache_dir / f"{safe_symbol}_{interval}.csv"


def cache_metadata_path(symbol: str, interval: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_path(symbol, interval, cache_dir).with_suffix(".metadata.json")


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
    df = df.dropna(subset=["timestamp"]).reset_index(drop=True)
    metadata = _load_cache_metadata(symbol, interval, cache_dir)
    metadata["source"] = "cache"
    metadata["symbol"] = symbol
    metadata["interval"] = interval
    metadata["warnings"] = _cache_warnings(metadata)
    return attach_provider_metadata(df, metadata)


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
    _save_cache_metadata(df, symbol, interval, cache_dir)
    return path


def _load_cache_metadata(symbol: str, interval: str, cache_dir: Path) -> dict:
    path = cache_metadata_path(symbol, interval, cache_dir)
    if not path.exists():
        return {
            "provider": "local_cache",
            "period": None,
            "retrieved_at": None,
            "adjusted": None,
            "warnings": ["Loaded from local CSV cache; provider retrieval metadata is not persisted"],
        }
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {
            "provider": "local_cache",
            "period": None,
            "retrieved_at": None,
            "adjusted": None,
            "warnings": ["Cache metadata sidecar could not be read"],
        }


def _save_cache_metadata(df: pd.DataFrame, symbol: str, interval: str, cache_dir: Path) -> None:
    metadata = provider_metadata_from_df(df)
    metadata.update(
        {
            "symbol": symbol,
            "interval": interval,
            "source": "cache",
            "cached_at": pd.Timestamp.now(tz="UTC").isoformat(),
        }
    )
    cache_metadata_path(symbol, interval, cache_dir).write_text(
        json.dumps(metadata, indent=2, sort_keys=True)
    )


def _cache_warnings(metadata: dict) -> list[str]:
    warnings = list(metadata.get("warnings") or [])
    cache_warning = "Loaded from local CSV cache"
    if cache_warning not in warnings:
        warnings.append(cache_warning)
    return warnings
