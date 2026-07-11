from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from api.market_data import _alpaca_headers, _request


ALPACA_BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"
DEFAULT_LOOKBACK_DAYS = 550
DEFAULT_BAR_LIMIT = 260
MAX_PAGE_SIZE = 10_000
MAX_TOTAL_BARS = 10_000


def _parse_bar(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return {
            "timestamp": row.get("t"),
            "open": float(row["o"]),
            "high": float(row["h"]),
            "low": float(row["l"]),
            "close": float(row["c"]),
            "volume": float(row.get("v") or 0),
            "trade_count": int(row.get("n") or 0),
            "vwap": float(row.get("vw") or row["c"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def get_daily_bars(
    symbol: str,
    limit: int = DEFAULT_BAR_LIMIT,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> Dict[str, Any]:
    symbol = str(symbol).strip().upper()
    headers = _alpaca_headers()
    requested_limit = max(1, min(int(limit), MAX_TOTAL_BARS))
    requested_lookback = max(30, min(int(lookback_days), 20 * 365))

    if not headers:
        return {
            "ok": False,
            "symbol": symbol,
            "bars": [],
            "bar_count": 0,
            "source": "alpaca_historical_bars",
            "error": "Alpaca API credentials are not configured.",
        }

    feed = os.getenv("ALPACA_DATA_FEED", "iex").strip() or "iex"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=requested_lookback)
    page_token: Optional[str] = None
    pages = 0
    bars_by_timestamp: Dict[str, Dict[str, Any]] = {}

    try:
        while len(bars_by_timestamp) < requested_limit:
            remaining = requested_limit - len(bars_by_timestamp)
            params = {
                "symbols": symbol,
                "timeframe": "1Day",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": min(MAX_PAGE_SIZE, max(1, remaining)),
                "adjustment": "all",
                "feed": feed,
                # Fetch newest bars first. The previous ascending request could
                # stop after collecting the oldest 260 bars in a longer window.
                "sort": "desc",
            }
            if page_token:
                params["page_token"] = page_token

            payload = json.loads(
                _request(
                    ALPACA_BARS_URL + "?" + urlencode(params),
                    "application/json",
                    headers=headers,
                ).decode("utf-8")
            )
            pages += 1

            raw_container = payload.get("bars") or {}
            if isinstance(raw_container, dict):
                raw_bars = raw_container.get(symbol) or []
            elif isinstance(raw_container, list):
                raw_bars = raw_container
            else:
                raw_bars = []

            for row in raw_bars:
                parsed = _parse_bar(row)
                if parsed and parsed.get("timestamp"):
                    bars_by_timestamp[str(parsed["timestamp"])] = parsed

            page_token = payload.get("next_page_token")
            if not page_token:
                break

        ordered = sorted(
            bars_by_timestamp.values(),
            key=lambda row: str(row.get("timestamp", "")),
        )
        bars = ordered[-requested_limit:]

        return {
            "ok": bool(bars),
            "symbol": symbol,
            "bars": bars,
            "bar_count": len(bars),
            "requested_limit": requested_limit,
            "lookback_days": requested_lookback,
            "pages_fetched": pages,
            "source": "alpaca_historical_bars",
            "feed": feed,
            "adjustment": "all",
            "sort": "latest_first_then_chronological",
            "first_bar": bars[0].get("timestamp") if bars else None,
            "last_bar": bars[-1].get("timestamp") if bars else None,
            "error": None if bars else "No usable historical bars returned.",
        }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        return {
            "ok": False,
            "symbol": symbol,
            "bars": [],
            "bar_count": 0,
            "requested_limit": requested_limit,
            "lookback_days": requested_lookback,
            "pages_fetched": pages,
            "source": "alpaca_historical_bars",
            "feed": feed,
            "adjustment": "all",
            "error": str(error),
        }
