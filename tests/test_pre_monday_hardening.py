import json
import os
import threading
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from api import historical_data, pre_monday_hardening, shadow_mode


class DummyRouter:
    def get(self, *_args, **_kwargs):
        return lambda function: function

    def post(self, *_args, **_kwargs):
        return lambda function: function


class AliveThread:
    def is_alive(self):
        return True


class HardeningDummyApp:
    def __init__(self):
        self.app = DummyRouter()
        self._pre_monday_hardening_installed = False
        self._autonomous_thread = AliveThread()
        self._autonomous_stop_event = threading.Event()
        self._autonomous_state = {
            "running": True,
            "cycles": 3,
            "failures": 0,
            "last_run": "2026-07-11T00:00:00+00:00",
            "last_error": None,
            "last_status": "SHADOW_CYCLE_COMPLETE",
            "last_selected_symbol": "AAPL",
            "last_action": "SHADOW_BUY",
            "last_reason": "Shadow buy recorded.",
        }
        self.buy_called = False
        self._place_paper_buy = self._real_buy
        self.run_autonomous_cycle = lambda: {
            "last_status": "CYCLE_COMPLETE",
            "last_action": "BUY",
        }

    def _real_buy(self, _candidate):
        self.buy_called = True
        return {"ok": True}

    def _now(self):
        return "naive-time"


class ShadowCycleDummyApp:
    def __init__(self):
        self.app = DummyRouter()
        self.prices = {"AAPL": 100.0}
        self.watchlist = ["AAPL"]
        self.config = {
            "interval_seconds": 60,
            "max_position_value": 1500.0,
            "max_open_positions": 3,
            "min_confidence": 70,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06,
        }
        self.account = {
            "balance": 10_000.0,
            "equity": 10_000.0,
            "buying_power": 10_000.0,
            "mode": "paper",
        }
        self.positions = []
        self.trades = []
        self.equity_curve = [{"timestamp": "2026-07-10T20:00:00+00:00", "equity": 10_000.0}]
        self._autonomous_thread = None
        self._autonomous_stop_event = threading.Event()
        self._autonomous_lock = threading.RLock()
        self._autonomous_state = {
            "running": False,
            "cycles": 0,
            "failures": 0,
            "last_run": None,
            "last_error": None,
            "last_status": "IDLE",
            "last_selected_symbol": None,
            "last_action": None,
            "last_reason": None,
        }
        self.events = []
        self.real_buy_called = False
        self._score_symbol = self._score
        self._place_paper_buy = self._real_buy
        self._manage_positions = lambda: []
        self.run_autonomous_cycle = self._cycle
        self.start_autonomous_trader = lambda: self.autonomous_status()
        self.stop_autonomous_trader = lambda: self.autonomous_status()

    def _score(self, symbol):
        return {
            "symbol": symbol,
            "price": 100.0,
            "score": 90,
            "confidence": 90,
            "threshold": 70,
            "approved": True,
            "action": "BUY",
            "reason": "Test signal.",
            "technical": {"ok": True},
            "hard_filters": {},
            "components": {},
            "market_regime": {"regime": "BULLISH", "trade_allowed": True},
            "risk_model": {
                "risk_per_trade_pct": 0.005,
                "stop_loss_pct": 0.03,
                "take_profit_pct": 0.06,
            },
        }

    def _real_buy(self, _candidate):
        self.real_buy_called = True
        self.account["balance"] -= 100.0
        self.positions.append({"symbol": "AAPL"})
        return {"ok": True, "real": True}

    def _cycle(self):
        self._autonomous_state["cycles"] += 1
        candidate = self._score_symbol("AAPL")
        order_result = self._place_paper_buy(candidate)
        self._autonomous_state.update(
            {
                "last_status": "CYCLE_COMPLETE" if order_result["ok"] else "REJECTED",
                "last_action": "BUY" if order_result["ok"] else "NO_TRADE",
                "last_selected_symbol": "AAPL",
                "last_reason": order_result.get("message"),
            }
        )
        return self.autonomous_status(
            extra={"selected": candidate, "order_result": order_result}
        )

    def _normalize_symbol(self, symbol):
        return str(symbol).strip().upper()

    def _open_position(self, symbol):
        return next((row for row in self.positions if row["symbol"] == symbol), None)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def _append_decision(self, event_type, payload):
        event = {"event_type": event_type, **deepcopy(payload)}
        self.events.append(event)
        return event

    def _save_state(self):
        return None

    def _ensure_data_dir(self):
        return None

    def _refresh_equity(self, record=True):
        return self.account["equity"]

    def autonomous_status(self, extra=None):
        payload = {**self._autonomous_state, "account": deepcopy(self.account)}
        if extra:
            payload["details"] = extra
        return payload


class LatestHistoricalBarsTests(unittest.TestCase):
    def test_loader_returns_latest_requested_bars(self):
        rows = [
            {
                "t": f"2026-01-0{day}T00:00:00Z",
                "o": day,
                "h": day + 1,
                "l": day - 1,
                "c": day,
                "v": 100,
            }
            for day in range(1, 6)
        ]
        response = json.dumps(
            {"bars": {"AAPL": rows}, "next_page_token": None}
        ).encode()

        with patch.object(
            historical_data,
            "_alpaca_headers",
            return_value={"x": "y"},
        ), patch.object(
            historical_data,
            "_request",
            return_value=response,
        ) as request:
            result = historical_data.get_daily_bars(
                "AAPL",
                limit=3,
                lookback_days=1000,
            )

        self.assertEqual(result["bar_count"], 3)
        self.assertEqual(
            [bar["timestamp"] for bar in result["bars"]],
            [
                "2026-01-03T00:00:00Z",
                "2026-01-04T00:00:00Z",
                "2026-01-05T00:00:00Z",
            ],
        )
        self.assertIn("sort=desc", request.call_args.args[0])


class FreshnessTests(unittest.TestCase):
    def test_stale_history_is_removed_and_fails_closed(self):
        stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        payload = {
            "ok": True,
            "bars": [{"timestamp": stale, "close": 100.0}],
            "bar_count": 1,
        }
        with patch.dict(os.environ, {"KYLE_MAX_HISTORY_AGE_DAYS": "10"}):
            result = pre_monday_hardening._history_payload_with_freshness(payload)

        self.assertFalse(result["ok"])
        self.assertFalse(result["history_fresh"])
        self.assertEqual(result["bars"], [])
        self.assertEqual(result["stale_bar_count"], 1)

    def test_recent_history_remains_available(self):
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        payload = {
            "ok": True,
            "bars": [{"timestamp": recent, "close": 100.0}],
            "bar_count": 1,
        }
        result = pre_monday_hardening._history_payload_with_freshness(payload)

        self.assertTrue(result["ok"])
        self.assertTrue(result["history_fresh"])
        self.assertEqual(len(result["bars"]), 1)

    def test_market_refresh_always_includes_regime_symbols(self):
        symbols = pre_monday_hardening._symbols_with_regime(["AAPL"])
        self.assertEqual(symbols, {"AAPL", "SPY", "QQQ"})


class ExecutionHardeningTests(unittest.TestCase):
    def test_operator_stop_cancels_inflight_execution(self):
        app = HardeningDummyApp()
        app._autonomous_stop_event.set()
        pre_monday_hardening.install_pre_monday_hardening(app)

        result = app._place_paper_buy({"symbol": "AAPL"})

        self.assertFalse(result["ok"])
        self.assertTrue(result["execution_cancelled"])
        self.assertFalse(result["real_order_submitted"])
        self.assertFalse(app.buy_called)

    def test_cycle_response_is_synchronized_with_authoritative_state(self):
        app = HardeningDummyApp()
        pre_monday_hardening.install_pre_monday_hardening(app)

        result = app.run_autonomous_cycle()

        self.assertEqual(result["last_status"], "SHADOW_CYCLE_COMPLETE")
        self.assertEqual(result["last_action"], "SHADOW_BUY")
        self.assertTrue(result["pre_monday_hardening"]["history_freshness_enforced"])


class FullShadowPipelineTests(unittest.TestCase):
    def setUp(self):
        shadow_mode._shadow_state.clear()
        shadow_mode._shadow_state.update(shadow_mode._empty_state())

    def tearDown(self):
        shadow_mode._shadow_state.clear()
        shadow_mode._shadow_state.update(shadow_mode._empty_state())

    def test_full_cycle_cannot_mutate_actual_paper_account(self):
        app = ShadowCycleDummyApp()
        actual_before = deepcopy(app.account)
        with patch.object(shadow_mode, "_load_shadow_state"), patch.object(
            shadow_mode,
            "_save_shadow_state",
        ):
            shadow_mode.install_shadow_mode(app)
            pre_monday_hardening.install_pre_monday_hardening(app)
            shadow_mode._shadow_state["enabled"] = True
            result = app.run_autonomous_cycle()

        self.assertFalse(app.real_buy_called)
        self.assertEqual(app.account, actual_before)
        self.assertEqual(app.positions, [])
        self.assertEqual(len(shadow_mode._shadow_state["positions"]), 1)
        self.assertFalse(
            result["details"]["order_result"]["real_order_submitted"]
        )
        self.assertEqual(result["last_status"], "SHADOW_CYCLE_COMPLETE")
        self.assertEqual(result["last_action"], "SHADOW_BUY")


if __name__ == "__main__":
    unittest.main()
