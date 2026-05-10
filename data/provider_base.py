from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd


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


class MarketDataProvider(ABC):
    @abstractmethod
    def get_intraday(self, symbol: str, interval: str = "1m") -> pd.DataFrame:
        """
        Return DataFrame with columns:
        timestamp, open, high, low, close, volume
        """
        raise NotImplementedError
