import os

from backend.market_data.cache import cache
from backend.market_data.simulation_provider import SimulationMarketDataProvider
from backend.universe import SYMBOLS

_provider = None
_provider_name = None
_last_error = None


def _load_provider():
    global _provider, _provider_name, _last_error

    configured = os.getenv("MARKET_DATA_PROVIDER", "simulation").lower()

    if _provider and _provider_name == configured:
        return _provider

    try:
        if configured == "alpaca":
            from backend.market_data.alpaca_provider import AlpacaMarketDataProvider

            _provider = AlpacaMarketDataProvider()
            _provider_name = configured
            _last_error = None
            return _provider

        _provider = SimulationMarketDataProvider()
        _provider_name = configured
        _last_error = None
        return _provider

    except Exception as error:
        _provider = SimulationMarketDataProvider()
        _provider_name = "simulation"
        _last_error = str(error)
        return _provider


def provider_status():
    provider = _load_provider()
    market_status = provider.get_market_status()

    return {
        "provider": provider.name,
        "configured_provider": os.getenv("MARKET_DATA_PROVIDER", "simulation"),
        "fallback_error": _last_error,
        "market": market_status,
    }


def get_watchlist():
    provider = _load_provider()
    return provider.get_watchlist()


def get_price(symbol: str):
    symbol = symbol.upper()
    cache_key = f"price:{symbol}"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    provider = _load_provider()
    price = provider.get_price(symbol)

    return cache.set(cache_key, price)


def get_prices(symbols=None):
    symbols = symbols or SYMBOLS
    normalized = [symbol.upper() for symbol in symbols]
    cache_key = "prices:" + ",".join(sorted(normalized))
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    provider = _load_provider()
    prices = provider.get_prices(normalized)

    # Compatibility bridge: keep backend.market.prices updated so older modules
    # continue to work while we migrate them one-by-one to this service.
    try:
        from backend import market as legacy_market

        legacy_market.prices.update(prices)
    except Exception:
        pass

    return cache.set(cache_key, prices)


def get_quote(symbol: str):
    symbol = symbol.upper()
    cache_key = f"quote:{symbol}"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    provider = _load_provider()
    quote = provider.get_quote(symbol)

    return cache.set(cache_key, quote)


def get_snapshot(symbol: str):
    symbol = symbol.upper()
    cache_key = f"snapshot:{symbol}"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    provider = _load_provider()
    snapshot = provider.get_snapshot(symbol)

    return cache.set(cache_key, snapshot)


def get_candles(symbol: str, limit: int = 120):
    symbol = symbol.upper()
    cache_key = f"candles:{symbol}:{limit}"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    provider = _load_provider()
    candles = provider.get_candles(symbol, limit=limit)

    if not candles:
        try:
            from backend import market as legacy_market

            candles = legacy_market.candles.get(symbol, [])[-limit:]
        except Exception:
            candles = []

    return cache.set(cache_key, candles)


def refresh():
    cache.clear()
    prices = get_prices()

    return {
        "status": "refreshed",
        "provider": _load_provider().name,
        "symbols": len(prices),
        "prices": prices,
    }
