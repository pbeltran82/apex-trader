from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import json
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval=1m&range=1d&includePrePost=false"
)
STOOQ_QUOTE_URL = "https://stooq.com/q/l/?s={symbol}.us&f=sd2t2ohlcv&h&e=csv"
REQUEST_TIMEOUT_SECONDS = 8


def _request(url: str, accept: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36"
            ),
            "Accept": accept,
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def _fetch_yahoo_price(symbol: str) -> Dict[str, Any]:
    try:
        payload = json.loads(
            _request(
                YAHOO_CHART_URL.format(symbol=symbol),
                "application/json",
            ).decode("utf-8")
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        return {
            "symbol": symbol,
            "ok": False,
            "source": "yahoo_chart",
            "error": str(error),
        }

    try:
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice")

        if price is None:
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            price = next((value for value in reversed(closes) if value is not None), None)

        if price is None or float(price) <= 0:
            raise ValueError("No valid market price returned.")

        market_timestamp = meta.get("regularMarketTime")
        observed_at: Optional[str] = None
        if market_timestamp:
            observed_at = datetime.fromtimestamp(
                int(market_timestamp), tz=timezone.utc
            ).isoformat()

        return {
            "symbol": symbol,
            "ok": True,
            "price": round(float(price), 2),
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName"),
            "market_state": meta.get("marketState"),
            "observed_at": observed_at,
            "source": "yahoo_chart",
        }
    except (KeyError, IndexError, TypeError, ValueError) as error:
        return {
            "symbol": symbol,
            "ok": False,
            "source": "yahoo_chart",
            "error": str(error),
        }


def _fetch_stooq_price(symbol: str) -> Dict[str, Any]:
    try:
        text = _request(
            STOOQ_QUOTE_URL.format(symbol=symbol.lower()),
            "text/csv",
        ).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows:
            raise ValueError("No quote row returned.")

        row = rows[0]
        close_raw = row.get("Close")
        if close_raw in (None, "", "N/D"):
            raise ValueError("No valid close price returned.")

        price = float(close_raw)
        if price <= 0:
            raise ValueError("Market price must be positive.")

        observed_at = None
        quote_date = row.get("Date")
        quote_time = row.get("Time")
        if quote_date and quote_date != "N/D":
            stamp = f"{quote_date}T{quote_time or '00:00:00'}"
            observed_at = stamp

        return {
            "symbol": symbol,
            "ok": True,
            "price": round(price, 2),
            "currency": "USD",
            "exchange": "US",
            "market_state": "DELAYED_OR_LAST",
            "observed_at": observed_at,
            "source": "stooq_csv",
        }
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, ValueError) as error:
        return {
            "symbol": symbol,
            "ok": False,
            "source": "stooq_csv",
            "error": str(error),
        }


def _fetch_price_with_fallback(symbol: str) -> Dict[str, Any]:
    yahoo = _fetch_yahoo_price(symbol)
    if yahoo.get("ok"):
        yahoo["attempts"] = [
            {"source": "yahoo_chart", "ok": True},
        ]
        return yahoo

    stooq = _fetch_stooq_price(symbol)
    stooq["attempts"] = [
        {
            "source": "yahoo_chart",
            "ok": False,
            "error": yahoo.get("error"),
        },
        {
            "source": "stooq_csv",
            "ok": bool(stooq.get("ok")),
            "error": stooq.get("error"),
        },
    ]
    return stooq


def refresh_market_prices(symbols: Iterable[str]) -> Dict[str, Any]:
    unique_symbols = sorted(
        {str(symbol).strip().upper() for symbol in symbols if symbol}
    )

    # Fetch sequentially. This is intentionally conservative because public
    # quote endpoints commonly rate-limit cloud-hosted IP ranges.
    results = [_fetch_price_with_fallback(symbol) for symbol in unique_symbols]

    successful = {
        row["symbol"]: row["price"]
        for row in results
        if row.get("ok") and row.get("price") is not None
    }

    active_sources = sorted(
        {row.get("source") for row in results if row.get("ok") and row.get("source")}
    )

    return {
        "requested": unique_symbols,
        "updated": successful,
        "results": results,
        "sources": active_sources,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


def install_market_data(app_module: Any) -> None:
    """Wrap Kyle's autonomous cycle with a market-price refresh.

    Yahoo is attempted first. Stooq is used automatically when Yahoo rejects
    the Oracle VM or otherwise fails. The existing cycle then marks positions
    to market, recalculates equity, and applies stop-loss/take-profit exits.
    """

    if getattr(app_module, "_market_data_installed", False):
        return

    original_run_cycle = app_module.run_autonomous_cycle

    def run_cycle_with_market_data() -> Dict[str, Any]:
        symbols = set(app_module.watchlist)
        symbols.update(position["symbol"] for position in app_module.positions)
        refresh = refresh_market_prices(symbols)

        changed = {}
        for symbol, new_price in refresh["updated"].items():
            old_price = app_module.prices.get(symbol)
            app_module.prices[symbol] = new_price
            if old_price != new_price:
                changed[symbol] = {"old": old_price, "new": new_price}

        app_module._append_decision(
            "MARKET_DATA_REFRESH",
            {
                "sources": refresh["sources"],
                "changed": changed,
                "results": refresh["results"],
            },
        )

        result = original_run_cycle()
        result["market_data"] = {
            "sources": refresh["sources"],
            "changed": changed,
            "refreshed_at": refresh["refreshed_at"],
        }
        return result

    app_module.run_autonomous_cycle = run_cycle_with_market_data
    app_module._market_data_installed = True
