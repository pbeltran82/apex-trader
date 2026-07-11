from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

from api.market_data import _alpaca_headers, _request


ALPACA_BARS_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
DEFAULT_LOOKBACK_DAYS = 550
DEFAULT_BAR_LIMIT = 260


def get_daily_bars(symbol: str, limit: int = DEFAULT_BAR_LIMIT) -> Dict[str, Any]:
    symbol = str(symbol).strip().upper()
    headers = _alpaca_headers()
    if not headers:
        return {
            "ok": False,
            "symbol": symbol,
            "bars": [],
            "source": "alpaca_historical_bars",
            "error": "Alpaca API credentials are not configured.",
        }

    feed = os.getenv("ALPACA_DATA_FEED", "iex").strip() or "iex"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    params = {
        "timeframe": "1Day",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "limit": max(1, min(int(limit), 10000)),
        "adjustment": "raw",
        "feed": feed,
        "sort": "asc",
    }
    url = ALPACA_BARS_URL.format(symbol=quote(symbol)) + "?" + urlencode(params)

    try:
        payload = json.loads(
            _request(url, "application/json", headers=headers).decode("utf-8")
        )
        raw_bars = payload.get("bars") or []
        bars: List[Dict[str, Any]] = []
        for row in raw_bars:
            try:
                bars.append(
                    {
                        "timestamp": row.get("t"),
                        "open": float(row["o"]),
                        "high": float(row["h"]),
                        "low": float(row["l"]),
                        "close": float(row["c"]),
                        "volume": float(row.get("v") or 0),
                        "trade_count": int(row.get("n") or 0),
                        "vwap": float(row.get("vw") or row["c"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue

        return {
            "ok": bool(bars),
            "symbol": symbol,
            "bars": bars,
            "bar_count": len(bars),
            "source": "alpaca_historical_bars",
            "feed": feed,
            "error": None if bars else "No usable historical bars returned.",
        }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        return {
            "ok": False,
            "symbol": symbol,
            "bars": [],
            "bar_count": 0,
            "source": "alpaca_historical_bars",
            "feed": feed,
            "error": str(error),
        }
