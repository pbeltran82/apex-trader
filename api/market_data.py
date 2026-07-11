from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import json
import os
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ALPACA_LATEST_TRADE_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest"
ALPACA_CLOCK_URL = "https://paper-api.alpaca.markets/v2/clock"
YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval=1m&range=1d&includePrePost=false"
)
STOOQ_QUOTE_URL = "https://stooq.com/q/l/?s={symbol}.us&f=sd2t2ohlcv&h&e=csv"
REQUEST_TIMEOUT_SECONDS = 8
DEFAULT_MAX_QUOTE_AGE_SECONDS = 300


def _request(url: str, accept: str, headers: Optional[Dict[str, str]] = None) -> bytes:
    request_headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 Chrome/124 Safari/537.36"
        ),
        "Accept": accept,
        "Cache-Control": "no-cache",
    }
    if headers:
        request_headers.update(headers)

    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def _alpaca_credentials() -> tuple[Optional[str], Optional[str]]:
    key = (
        os.getenv("ALPACA_API_KEY_ID")
        or os.getenv("APCA_API_KEY_ID")
        or os.getenv("ALPACA_API_KEY")
    )
    secret = (
        os.getenv("ALPACA_API_SECRET_KEY")
        or os.getenv("APCA_API_SECRET_KEY")
        or os.getenv("ALPACA_SECRET_KEY")
    )
    return key, secret


def _alpaca_headers() -> Optional[Dict[str, str]]:
    key, secret = _alpaca_credentials()
    if not key or not secret:
        return None
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    }


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _quote_age_seconds(observed_at: Optional[str]) -> Optional[float]:
    observed = _parse_timestamp(observed_at)
    if observed is None:
        return None
    return max(0.0, round((datetime.now(timezone.utc) - observed).total_seconds(), 2))


def _max_quote_age_seconds() -> int:
    raw = os.getenv("KYLE_MAX_QUOTE_AGE_SECONDS", str(DEFAULT_MAX_QUOTE_AGE_SECONDS))
    try:
        return max(30, int(raw))
    except ValueError:
        return DEFAULT_MAX_QUOTE_AGE_SECONDS


def _fetch_alpaca_clock() -> Dict[str, Any]:
    headers = _alpaca_headers()
    if not headers:
        return {
            "ok": False,
            "source": "alpaca_clock",
            "error": "Alpaca API credentials are not configured.",
        }

    try:
        payload = json.loads(
            _request(ALPACA_CLOCK_URL, "application/json", headers=headers).decode("utf-8")
        )
        return {
            "ok": True,
            "source": "alpaca_clock",
            "is_open": bool(payload.get("is_open")),
            "timestamp": payload.get("timestamp"),
            "next_open": payload.get("next_open"),
            "next_close": payload.get("next_close"),
        }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        return {
            "ok": False,
            "source": "alpaca_clock",
            "error": str(error),
        }


def _fetch_alpaca_price(symbol: str) -> Dict[str, Any]:
    headers = _alpaca_headers()
    if not headers:
        return {
            "symbol": symbol,
            "ok": False,
            "source": "alpaca_market_data",
            "error": "Alpaca API credentials are not configured.",
        }

    feed = os.getenv("ALPACA_DATA_FEED", "iex").strip() or "iex"
    url = (
        ALPACA_LATEST_TRADE_URL.format(symbol=quote(symbol))
        + "?"
        + urlencode({"feed": feed})
    )

    try:
        payload = json.loads(
            _request(
                url,
                "application/json",
                headers=headers,
            ).decode("utf-8")
        )
        trade = payload.get("trade") or {}
        price = trade.get("p")
        if price is None or float(price) <= 0:
            raise ValueError("No valid latest trade price returned.")

        observed_at = trade.get("t")
        return {
            "symbol": symbol,
            "ok": True,
            "price": round(float(price), 2),
            "currency": "USD",
            "exchange": trade.get("x"),
            "market_state": "LATEST_TRADE",
            "observed_at": observed_at,
            "age_seconds": _quote_age_seconds(observed_at),
            "source": "alpaca_market_data",
            "feed": feed,
        }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        return {
            "symbol": symbol,
            "ok": False,
            "source": "alpaca_market_data",
            "error": str(error),
            "feed": feed,
        }


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
            "age_seconds": _quote_age_seconds(observed_at),
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
            observed_at = f"{quote_date}T{quote_time or '00:00:00'}"

        return {
            "symbol": symbol,
            "ok": True,
            "price": round(price, 2),
            "currency": "USD",
            "exchange": "US",
            "market_state": "DELAYED_OR_LAST",
            "observed_at": observed_at,
            "age_seconds": _quote_age_seconds(observed_at),
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
    attempts = []

    providers = (
        ("alpaca_market_data", _fetch_alpaca_price),
        ("yahoo_chart", _fetch_yahoo_price),
        ("stooq_csv", _fetch_stooq_price),
    )

    last_result: Dict[str, Any] = {
        "symbol": symbol,
        "ok": False,
        "source": "none",
        "error": "No market data provider succeeded.",
    }

    for provider_name, provider in providers:
        result = provider(symbol)
        attempts.append(
            {
                "source": provider_name,
                "ok": bool(result.get("ok")),
                "error": result.get("error"),
            }
        )
        last_result = result
        if result.get("ok"):
            result["attempts"] = attempts
            return result

    last_result["attempts"] = attempts
    return last_result


def refresh_market_prices(symbols: Iterable[str]) -> Dict[str, Any]:
    unique_symbols = sorted(
        {str(symbol).strip().upper() for symbol in symbols if symbol}
    )

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


def evaluate_market_gate(refresh: Dict[str, Any]) -> Dict[str, Any]:
    clock = _fetch_alpaca_clock()
    max_age = _max_quote_age_seconds()

    if not clock.get("ok"):
        return {
            "allowed": False,
            "status": "MARKET_DATA_UNAVAILABLE",
            "reason": "Kyle could not verify the official market clock; new entries are blocked.",
            "clock": clock,
            "max_quote_age_seconds": max_age,
            "stale_symbols": [],
            "missing_symbols": refresh.get("requested", []),
        }

    if not clock.get("is_open"):
        return {
            "allowed": False,
            "status": "MARKET_CLOSED",
            "reason": "The U.S. equity market is closed; Kyle will not open new positions.",
            "clock": clock,
            "max_quote_age_seconds": max_age,
            "stale_symbols": [],
            "missing_symbols": [],
        }

    authenticated_results = {
        row.get("symbol"): row
        for row in refresh.get("results", [])
        if row.get("ok") and row.get("source") == "alpaca_market_data"
    }
    missing_symbols = [
        symbol
        for symbol in refresh.get("requested", [])
        if symbol not in authenticated_results
    ]
    stale_symbols = [
        symbol
        for symbol, row in authenticated_results.items()
        if row.get("age_seconds") is None or row.get("age_seconds") > max_age
    ]

    if missing_symbols:
        return {
            "allowed": False,
            "status": "MARKET_DATA_UNAVAILABLE",
            "reason": "Authenticated Alpaca quotes are missing; new entries are blocked.",
            "clock": clock,
            "max_quote_age_seconds": max_age,
            "stale_symbols": stale_symbols,
            "missing_symbols": missing_symbols,
        }

    if stale_symbols:
        return {
            "allowed": False,
            "status": "STALE_MARKET_DATA",
            "reason": "One or more authenticated quotes are stale; new entries are blocked.",
            "clock": clock,
            "max_quote_age_seconds": max_age,
            "stale_symbols": stale_symbols,
            "missing_symbols": [],
        }

    return {
        "allowed": True,
        "status": "MARKET_OPEN",
        "reason": "Market clock is open and authenticated quotes are fresh.",
        "clock": clock,
        "max_quote_age_seconds": max_age,
        "stale_symbols": [],
        "missing_symbols": [],
    }


def install_market_data(app_module: Any) -> None:
    """Install authenticated market refresh and a fail-closed entry gate.

    Existing positions are marked to the latest available price every cycle.
    Kyle only executes exits or opens new positions when Alpaca confirms the
    market is open and every requested authenticated quote is fresh.
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

        gate = evaluate_market_gate(refresh)
        app_module._append_decision(
            "MARKET_DATA_REFRESH",
            {
                "sources": refresh["sources"],
                "changed": changed,
                "results": refresh["results"],
                "gate": gate,
            },
        )

        if gate["allowed"]:
            result = original_run_cycle()
            result["market_data"] = {
                "sources": refresh["sources"],
                "changed": changed,
                "refreshed_at": refresh["refreshed_at"],
                "gate": gate,
            }
            return result

        with app_module._autonomous_lock:
            app_module._autonomous_state["cycles"] += 1
            app_module._autonomous_state["last_run"] = app_module._now()
            app_module._autonomous_state["last_error"] = None
            app_module._refresh_equity()
            app_module._autonomous_state.update(
                {
                    "last_status": gate["status"],
                    "last_action": "NO_TRADE",
                    "last_selected_symbol": None,
                    "last_reason": gate["reason"],
                }
            )
            decision = app_module._append_decision(
                "AUTONOMOUS_CYCLE",
                {
                    "status": gate["status"],
                    "action": "NO_TRADE",
                    "reason": gate["reason"],
                    "exit_updates": [],
                    "market_data": {
                        "sources": refresh["sources"],
                        "changed": changed,
                        "refreshed_at": refresh["refreshed_at"],
                        "gate": gate,
                    },
                },
            )
            app_module._save_state()
            return app_module.autonomous_status(
                extra={
                    "exit_updates": [],
                    "decision": decision,
                    "market_data": {
                        "sources": refresh["sources"],
                        "changed": changed,
                        "refreshed_at": refresh["refreshed_at"],
                        "gate": gate,
                    },
                }
            )

    app_module.run_autonomous_cycle = run_cycle_with_market_data
    app_module._market_data_installed = True

    @app_module.app.get("/api/market-data/status")
    def market_data_status():
        symbols = set(app_module.watchlist)
        symbols.update(position["symbol"] for position in app_module.positions)
        refresh = refresh_market_prices(symbols)
        return {
            "refresh": refresh,
            "gate": evaluate_market_gate(refresh),
        }
