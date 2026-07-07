from abc import ABC, abstractmethod


class MarketDataProvider(ABC):
    """Base interface for all market data providers."""

    name = "BASE"

    @abstractmethod
    def get_price(self, symbol: str):
        pass

    @abstractmethod
    def get_prices(self, symbols=None):
        pass

    @abstractmethod
    def get_quote(self, symbol: str):
        pass

    @abstractmethod
    def get_snapshot(self, symbol: str):
        pass

    @abstractmethod
    def get_candles(self, symbol: str, limit: int = 120):
        pass

    @abstractmethod
    def get_market_status(self):
        pass

    @abstractmethod
    def get_watchlist(self):
        pass
