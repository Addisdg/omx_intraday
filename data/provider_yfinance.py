from __future__ import annotations

import pandas as pd
import yfinance as yf

from data.cache import save_cached_data
from data.provider_base import (
    MarketDataProvider,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderSchemaError,
    ProviderTimeoutError,
)


class YFinanceProvider(MarketDataProvider):
    def get_intraday(
        self,
        symbol: str,
        interval: str = "1m",
        period: str | None = None,
        save_to_cache: bool = True,
    ) -> pd.DataFrame:
        period_map = {
            "1m": "1d",
            "2m": "1d",
            "5m": "5d",
            "15m": "5d",
            "30m": "1mo",
            "60m": "1mo",
        }

        try:
            df = yf.download(
                tickers=symbol,
                interval=interval,
                period=period or period_map.get(interval, "5d"),
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception as exc:
            raise _provider_error_from_exception(exc) from exc

        if df is None or df.empty:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df = df.reset_index()

        if "Datetime" in df.columns:
            df = df.rename(columns={"Datetime": "timestamp"})
        elif "Date" in df.columns:
            df = df.rename(columns={"Date": "timestamp"})

        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )

        needed = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ProviderSchemaError(
                f"Missing expected columns: {missing}. Got: {list(df.columns)}"
            )

        df = df[needed].copy()

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(
            subset=["timestamp", "open", "high", "low", "close"]
        ).reset_index(drop=True)
        if save_to_cache:
            save_cached_data(df, symbol, interval)
        return df

    def get_history(
        self,
        symbol: str,
        interval: str = "1d",
        period: str = "1y",
        save_to_cache: bool = True,
    ) -> pd.DataFrame:
        return self.get_intraday(
            symbol=symbol,
            interval=interval,
            period=period,
            save_to_cache=save_to_cache,
        )


def _provider_error_from_exception(exc: Exception) -> Exception:
    message = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in message or "timed out" in message:
        return ProviderTimeoutError(str(exc))
    if any(term in message for term in ["rate limit", "too many requests", "429"]):
        return ProviderRateLimitError(str(exc))
    if isinstance(exc, ConnectionError) or any(term in message for term in ["connection", "network", "dns", "name resolution"]):
        return ProviderConnectionError(str(exc))
    return exc
