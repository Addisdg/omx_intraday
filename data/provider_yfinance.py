from __future__ import annotations

import pandas as pd
import yfinance as yf

from data.cache import save_cached_data


class YFinanceProvider:
    def get_intraday(
        self,
        symbol: str,
        interval: str = "1m",
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

        df = yf.download(
            tickers=symbol,
            interval=interval,
            period=period_map.get(interval, "5d"),
            progress=False,
            auto_adjust=False,
            threads=False,
        )

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
            raise ValueError(
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
