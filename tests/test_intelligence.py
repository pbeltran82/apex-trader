import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from api import intelligence
from api.runtime_hardening import install_runtime_hardening


def build_bars(count=230, start_price=100.0, daily_step=0.25):
    bars = []
    start = datetime.now(timezone.utc) - timedelta(days=count + 10)
    previous = start_price
    for index in range(count):
        close = start_price + index * daily_step
        bars.append(
            {
                "timestamp": (start + timedelta(days=index)).isoformat(),
                "open": previous,
                "high": close + 1.0,
                "low": max(0.01, close - 1.0),
                "close": close,
                "volume": 1_000_000 + index * 1_000,
                "trade_count": 10_000,
                "vwap": close,
            }
        )
        previous = close
    return bars


class IntelligenceMathTests(unittest.TestCase):
    def setUp(self):
        intelligence._bars_cache.clear()
        intelligence._regime_cache.clear()

    def test_sma_uses_latest_period(self):
        self.assertEqual(intelligence._sma([1, 2, 3, 4, 5], 3), 4)

    def test_atr_is_positive_for_valid_bars(self):
        atr = intelligence._atr(build_bars(30), 14)
        self.assertIsNotNone(atr)
        self.assertGreater(atr, 0)

    def test_completed_bars_excludes_current_utc_day(self):
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)
        bars = [
            {"timestamp": yesterday.isoformat(), "close": 100},
            {"timestamp": today.isoformat(), "close": 101},
        ]
        completed = intelligence._completed_bars(bars)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["close"], 100)

    def test_uptrend_snapshot_uses_real_bar_values(self):
        bars = build_bars()
        current_price = bars[-1]["close"] + 1
        with patch.object(
            intelligence,
            "_load_bars",
            return_value={"ok": True, "bars": bars, "source": "test"},
        ):
            snapshot = intelligence._technical_snapshot("AAPL", current_price)
        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["scores"]["trend"], 30)
        self.assertGreater(snapshot["return20_pct"], 0)
        self.assertGreater(snapshot["return60_pct"], 0)

    def test_regime_fails_closed_when_index_history_is_missing(self):
        app = SimpleNamespace(prices={})
        with patch.object(
            intelligence,
            "_load_bars",
            return_value={"ok": False, "bars": [], "error": "missing"},
        ):
            regime = intelligence.market_regime(app)
        self.assertEqual(regime["regime"], "UNKNOWN")
        self.assertFalse(regime["trade_allowed"])


class RuntimeHardeningTests(unittest.TestCase):
    def test_decision_payload_is_frozen(self):
        events = []

        def append_event(event_type, payload):
            event = {"event_type": event_type, **payload}
            events.append(event)
            return event

        app = SimpleNamespace(
            trades=[],
            _append_decision=append_event,
            _score_symbol=lambda symbol: {
                "symbol": symbol,
                "action": "BUY",
                "approved": True,
            },
        )
        install_runtime_hardening(app)
        payload = {"account": {"balance": 10000}}
        result = app._append_decision("TEST", payload)
        payload["account"]["balance"] = 1
        self.assertEqual(events[0]["account"]["balance"], 10000)
        self.assertEqual(result["account"]["balance"], 10000)

    def test_recent_sell_blocks_reentry(self):
        sold_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        app = SimpleNamespace(
            trades=[
                {
                    "symbol": "AAPL",
                    "side": "SELL",
                    "timestamp": sold_at,
                    "reason": "test exit",
                    "realized_pnl": -10,
                }
            ],
            _append_decision=lambda event_type, payload: payload,
            _score_symbol=lambda symbol: {
                "symbol": symbol,
                "action": "BUY",
                "approved": True,
            },
        )
        install_runtime_hardening(app)
        candidate = app._score_symbol("AAPL")
        self.assertEqual(candidate["action"], "WAIT")
        self.assertFalse(candidate["approved"])
        self.assertTrue(candidate["cooldown"]["active"])


if __name__ == "__main__":
    unittest.main()
