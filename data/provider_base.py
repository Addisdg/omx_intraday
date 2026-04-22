from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    def get_intraday(self, symbol: str, interval: str = "1m") -> pd.DataFrame:
        """
        Return DataFrame with columns:
        timestamp, open, high, low, close, volume
        """
        raise NotImplementedError
