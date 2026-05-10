from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd


PROVIDER_METADATA_ATTR = "provider_metadata"


class MarketDataError(Exception):
    status = "provider_error"
    user_message = "Market-data provider failed for this symbol."


class ProviderTimeoutError(MarketDataError):
    status = "provider_timeout"
    user_message = "Market-data provider timed out for this symbol."


class ProviderConnectionError(MarketDataError):
    status = "provider_connection_error"
    user_message = "Market-data provider connection failed for this symbol."


class ProviderRateLimitError(MarketDataError):
    status = "provider_rate_limited"
    user_message = "Market-data provider rate-limited this request."


class ProviderSchemaError(MarketDataError):
    status = "provider_schema_error"
    user_message = "Market-data provider returned an unexpected data shape."


class ProviderUnexpectedError(MarketDataError):
    status = "provider_unexpected_error"
    user_message = "Market-data provider failed unexpectedly for this symbol."


def attach_provider_metadata(df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    df.attrs[PROVIDER_METADATA_ATTR] = {**metadata, "row_count": int(len(df))}
    return df


def provider_metadata_from_df(df: pd.DataFrame | None) -> dict:
    if df is None:
        return _default_provider_metadata(row_count=0)
    metadata = dict(df.attrs.get(PROVIDER_METADATA_ATTR, {}))
    if not metadata:
        return _default_provider_metadata(row_count=len(df))
    metadata["row_count"] = int(len(df))
    return metadata


def _default_provider_metadata(row_count: int) -> dict:
    return {
        "provider": "unknown",
        "source": "unknown",
        "symbol": None,
        "interval": None,
        "period": None,
        "row_count": int(row_count),
        "retrieved_at": None,
        "adjusted": None,
        "warnings": ["Provider metadata unavailable"],
    }


class MarketDataProvider(ABC):
    @abstractmethod
    def get_intraday(self, symbol: str, interval: str = "1m") -> pd.DataFrame:
        """
        Return DataFrame with columns:
        timestamp, open, high, low, close, volume
        """
        raise NotImplementedError
