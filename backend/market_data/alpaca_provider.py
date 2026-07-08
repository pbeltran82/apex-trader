import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from backend.market_data.provider import MarketDataProvider
from backend.universe import SYMBOLS

load_dotenv(Path("/workspaces/apex-trader/.env"), override=True)


MAX_STALE_SECONDS = 60 * 60 * 24 * 7
MIN_VALID_PRICE = 0.01
MAX_VALID_PRICE = 10000.0


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

    def _trade_time(self, trade):
        return getattr(trade, "timestamp", None) or getattr(trade, "t", None)

    def _age_seconds(self, timestamp):
        if not timestamp:
            return None

        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return round((datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds(), 2)

    def _validate_price(self, symbol, price, timestamp=None):
        if price is None:
            raise ValueError(f"{symbol} has no latest trade price")

        price = float(price)

        if price < MIN_VALID_PRICE:
            raise ValueError(f"{symbol} latest trade price is invalid: {price}")

        if price > MAX_VALID_PRICE:
            raise ValueError(f"{symbol} latest trade price is abnormally high: {price}")

        age_seconds = self._age_seconds(timestamp)

        if age_seconds is not None and age_seconds > MAX_STALE_SECONDS:
            raise ValueError(f"{symbol} latest trade is stale: {age_seconds} seconds old")

        return price

    def get_price(self, symbol: str):
        symbol = symbol.upper()
        trade = self.get_latest_trade(symbol)
        timestamp = self._trade_time(trade)
        return self._validate_price(symbol, getattr(trade, "price", None), timestamp)

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
        trade = self.get_latest_trade(symbol)
        timestamp = self._trade_time(trade)
        price = self._validate_price(symbol, getattr(trade, "price", None), timestamp)

        return {
            "symbol": symbol,
            "available": True,
            "provider": self.name,
            "price": price,
            "timestamp": str(timestamp) if timestamp else None,
            "age_seconds": self._age_seconds(timestamp),
            "bid": None,
            "ask": None,
            "validated": True,
        }

    def get_snapshot(self, symbol: str):
        symbol = symbol.upper()
        quote = self.get_quote(symbol)

        return {
            "symbol": symbol,
            "available": True,
            "provider": self.name,
            "price": quote["price"],
            "quote": quote,
            "last_candle": None,
            "validated": True,
        }

    def get_candles(self, symbol: str, limit: int = 120):
        # Historical bars come next. For now this stays empty so ATR can
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
            "validation": {
                "max_stale_seconds": MAX_STALE_SECONDS,
                "min_valid_price": MIN_VALID_PRICE,
                "max_valid_price": MAX_VALID_PRICE,
            },
        }

    def get_watchlist(self):
        return SYMBOLS
