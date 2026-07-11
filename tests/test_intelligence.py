import json
from pathlib import Path
import tempfile
import threading
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


def runtime_app(directory, trades=None, decision_log=None):
    data_dir = Path(directory)
    return SimpleNamespace(
        trades=list(trades or []),
        decision_log=list(decision_log or []),
        _score_symbol=lambda symbol: {
            "symbol": symbol,
            "action": "BUY",
            "approved": True,
        },
        _persistence_lock=threading.Lock(),
        _ensure_data_dir=lambda: data_dir.mkdir(parents=True, exist_ok=True),
        DECISION_LOG_FILE=data_dir / "decision_log.jsonl",
        _now=lambda: datetime.now(timezone.utc).isoformat(),
    )


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
    def test_decision_payload_is_frozen_and_ids_are_monotonic(self):
        with tempfile.TemporaryDirectory() as directory:
            app = runtime_app(directory, decision_log=[{"id": 498}])
            install_runtime_hardening(app)

            payload = {"account": {"balance": 10000}}
            first = app._append_decision("TEST", payload)
            payload["account"]["balance"] = 1
            second = app._append_decision("TEST_TWO", {"ok": True})

            self.assertEqual(first["id"], 499)
            self.assertEqual(second["id"], 500)
            self.assertEqual(app.decision_log[-2]["account"]["balance"], 10000)
            self.assertEqual(first["account"]["balance"], 10000)

            persisted = [
                json.loads(line)
                for line in app.DECISION_LOG_FILE.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([event["id"] for event in persisted], [499, 500])

    def test_recent_sell_blocks_reentry(self):
        sold_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        trades = [
            {
                "symbol": "AAPL",
                "side": "SELL",
                "timestamp": sold_at,
                "reason": "test exit",
                "realized_pnl": -10,
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            app = runtime_app(directory, trades=trades)
            install_runtime_hardening(app)
            candidate = app._score_symbol("AAPL")

        self.assertEqual(candidate["action"], "WAIT")
        self.assertFalse(candidate["approved"])
        self.assertTrue(candidate["cooldown"]["active"])


if __name__ == "__main__":
    unittest.main()
