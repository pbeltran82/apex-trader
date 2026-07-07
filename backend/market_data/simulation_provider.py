from backend.market_data.provider import MarketDataProvider
from backend.universe import SYMBOLS
from backend import market as simulated_market


class SimulationMarketDataProvider(MarketDataProvider):
    """Market data provider backed by Kyle's existing simulated market."""

    name = "SIMULATION"

    def get_price(self, symbol: str):
        symbol = symbol.upper()
        return simulated_market.prices.get(symbol)

    def get_prices(self, symbols=None):
        simulated_market.update_market()

        symbols = symbols or SYMBOLS

        return {
            symbol.upper(): simulated_market.prices.get(symbol.upper())
            for symbol in symbols
            if symbol.upper() in simulated_market.prices
        }

    def get_quote(self, symbol: str):
        symbol = symbol.upper()
        price = self.get_price(symbol)

        if price is None:
            return {
                "symbol": symbol,
                "available": False,
                "provider": self.name,
            }

        return {
            "symbol": symbol,
            "available": True,
            "provider": self.name,
            "price": price,
            "bid": price,
            "ask": price,
        }

    def get_snapshot(self, symbol: str):
        symbol = symbol.upper()
        price = self.get_price(symbol)
        candles = self.get_candles(symbol)
        last_candle = candles[-1] if candles else None

        return {
            "symbol": symbol,
            "available": price is not None,
            "provider": self.name,
            "price": price,
            "quote": self.get_quote(symbol),
            "last_candle": last_candle,
        }

    def get_candles(self, symbol: str, limit: int = 120):
        symbol = symbol.upper()
        return simulated_market.candles.get(symbol, [])[-limit:]

    def get_market_status(self):
        return {
            "provider": self.name,
            "market_open": True,
            "status": "SIMULATED_OPEN",
        }

    def get_watchlist(self):
        return SYMBOLS
