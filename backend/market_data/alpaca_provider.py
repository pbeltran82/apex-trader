import os
from pathlib import Path

from dotenv import load_dotenv

from backend.market_data.provider import MarketDataProvider
from backend.universe import SYMBOLS

load_dotenv(Path("/workspaces/apex-trader/.env"), override=True)


class AlpacaMarketDataProvider(MarketDataProvider):
    """Alpaca-backed market data provider.

    This provider only observes the market. It does not submit orders.
    Execution stays behind the broker abstraction layer.
    """

    name = "ALPACA"

    def __init__(self):
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY")

        # Lazy imports keep the app bootable if alpaca-py is not installed yet.
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient

        self.trading_client = TradingClient(
            api_key,
            secret_key,
            paper=True,
        )

        self.data_client = StockHistoricalDataClient(
            api_key,
            secret_key,
        )

    def get_price(self, symbol: str):
        symbol = symbol.upper()
        trade = self.get_latest_trade(symbol)
        return float(trade.price)

    def get_prices(self, symbols=None):
        symbols = symbols or SYMBOLS
        results = {}

        for symbol in symbols:
            try:
                results[symbol.upper()] = self.get_price(symbol)
            except Exception:
                continue

        return results

    def get_latest_trade(self, symbol: str):
        from alpaca.data.requests import StockLatestTradeRequest

        symbol = symbol.upper()

        request = StockLatestTradeRequest(
            symbol_or_symbols=symbol,
        )

        data = self.data_client.get_stock_latest_trade(request)
        return data[symbol]

    def get_quote(self, symbol: str):
        symbol = symbol.upper()
        price = self.get_price(symbol)

        return {
            "symbol": symbol,
            "available": True,
            "provider": self.name,
            "price": price,
            "bid": None,
            "ask": None,
        }

    def get_snapshot(self, symbol: str):
        symbol = symbol.upper()
        price = self.get_price(symbol)

        return {
            "symbol": symbol,
            "available": True,
            "provider": self.name,
            "price": price,
            "quote": self.get_quote(symbol),
            "last_candle": None,
        }

    def get_candles(self, symbol: str, limit: int = 120):
        # Historical bars come next. For Sprint 12 this stays empty so ATR can
        # continue using simulation candles until the bars adapter is added.
        return []

    def get_market_status(self):
        clock = self.trading_client.get_clock()

        return {
            "provider": self.name,
            "market_open": bool(clock.is_open),
            "status": "OPEN" if clock.is_open else "CLOSED",
            "timestamp": str(clock.timestamp),
            "next_open": str(clock.next_open),
            "next_close": str(clock.next_close),
        }

    def get_watchlist(self):
        return SYMBOLS
