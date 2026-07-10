from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval=1m&range=1d&includePrePost=false"
)
REQUEST_TIMEOUT_SECONDS = 5


def _fetch_yahoo_price(symbol: str) -> Dict[str, Any]:
    request = Request(
        YAHOO_CHART_URL.format(symbol=symbol),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        return {"symbol": symbol, "ok": False, "error": str(error)}

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
        return {"symbol": symbol, "ok": False, "error": str(error)}


def refresh_market_prices(symbols: Iterable[str]) -> Dict[str, Any]:
    unique_symbols = sorted({str(symbol).strip().upper() for symbol in symbols if symbol})
    results = []

    with ThreadPoolExecutor(max_workers=min(5, max(1, len(unique_symbols)))) as pool:
        futures = {pool.submit(_fetch_yahoo_price, symbol): symbol for symbol in unique_symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                results.append(future.result())
            except Exception as error:  # defensive isolation per symbol
                results.append({"symbol": symbol, "ok": False, "error": str(error)})

    successful = {
        row["symbol"]: row["price"]
        for row in results
        if row.get("ok") and row.get("price") is not None
    }

    return {
        "requested": unique_symbols,
        "updated": successful,
        "results": sorted(results, key=lambda row: row["symbol"]),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


def install_market_data(app_module: Any) -> None:
    """Wrap Kyle's autonomous cycle with a real market-price refresh.

    The existing cycle already marks positions to market, calculates equity,
    and checks stop-loss/take-profit exits. This wrapper updates the shared
    price map immediately before that existing logic runs.
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
                "source": "yahoo_chart",
                "changed": changed,
                "results": refresh["results"],
            },
        )

        result = original_run_cycle()
        result["market_data"] = {
            "source": "yahoo_chart",
            "changed": changed,
            "refreshed_at": refresh["refreshed_at"],
        }
        return result

    app_module.run_autonomous_cycle = run_cycle_with_market_data
    app_module._market_data_installed = True
