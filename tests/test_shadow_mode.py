import os
import threading
import unittest
from copy import deepcopy
from unittest.mock import patch

from api import research, shadow_mode
from api.research_execution import (
    intraday_exit_price,
    simulate_fold_with_entry_day_execution,
)


class EntryDayExecutionTests(unittest.TestCase):
    def test_stop_wins_when_entry_day_stop_and_target_both_touch(self):
        price, reason = intraday_exit_price(
            day_open=100.0,
            day_low=95.0,
            day_high=110.0,
            stop_loss=98.0,
            take_profit=106.0,
            entered_today=True,
        )
        self.assertEqual(price, 98.0)
        self.assertEqual(reason, "ENTRY_DAY_STOP_LOSS")

    def test_simulator_closes_entry_day_stop_instead_of_waiting(self):
        bars = [
            {
                "timestamp": "2026-01-05T00:00:00+00:00",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1_000_000,
            }
        ]
        features = {
            0: {
                "execution_date": "2026-01-05",
                "signal_price": 100.0,
                "sma50": 90.0,
                "sma200": 80.0,
                "return20": 0.10,
                "relative_strength60": 0.10,
                "score": 100,
                "atr_pct": 0.02,
                "regime": {"regime": "BULLISH", "trade_allowed": True},
            }
        }
        config = research.StrategyConfig(
            threshold=70,
            atr_multiplier=1.5,
            reward_risk=2.0,
            max_holding_bars=20,
            relative_strength_filter=False,
            trend_exit=True,
        )

        result = simulate_fold_with_entry_day_execution(
            "AAPL",
            bars,
            features,
            0,
            1,
            config,
        )

        self.assertEqual(result["performance"]["trade_count"], 1)
        self.assertLess(result["performance"]["ending_equity"], 10_000.0)


class DummyRouter:
    def get(self, *_args, **_kwargs):
        return lambda function: function

    def post(self, *_args, **_kwargs):
        return lambda function: function


class DummyAppModule:
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
        self.equity_curve = [{"timestamp": "2026-01-01", "equity": 10_000.0}]
        self._autonomous_lock = threading.RLock()
        self._autonomous_state = {
            "running": False,
            "cycles": 0,
            "last_run": None,
            "last_status": "IDLE",
            "last_action": None,
            "last_reason": None,
            "last_selected_symbol": None,
        }
        self.events = []
        self.real_buy_called = False
        self.real_start_called = False

        self._score_symbol = lambda symbol: {
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
        self._place_paper_buy = self._real_buy
        self._manage_positions = lambda: []
        self.run_autonomous_cycle = lambda: {"details": {}}
        self.start_autonomous_trader = self._real_start
        self.stop_autonomous_trader = lambda: self.autonomous_status()

    def _real_buy(self, _candidate):
        self.real_buy_called = True
        self.account["balance"] -= 100.0
        self.positions.append({"symbol": "AAPL"})
        return {"ok": True, "real": True}

    def _real_start(self):
        self.real_start_called = True
        return self.autonomous_status()

    def _normalize_symbol(self, symbol):
        return str(symbol).strip().upper()

    def _open_position(self, symbol):
        return next((row for row in self.positions if row["symbol"] == symbol), None)

    def _now(self):
        return "2026-01-05T15:00:00"

    def _append_decision(self, event_type, payload):
        event = {"event_type": event_type, **payload}
        self.events.append(event)
        return event

    def _save_state(self):
        return None

    def _ensure_data_dir(self):
        return None

    def _refresh_equity(self, record=True):
        return self.account["equity"]

    def autonomous_status(self, extra=None):
        payload = {**self._autonomous_state, "account": self.account}
        if extra:
            payload["details"] = extra
        return payload


class ShadowIsolationTests(unittest.TestCase):
    def setUp(self):
        shadow_mode._shadow_state.clear()
        shadow_mode._shadow_state.update(shadow_mode._empty_state())

    def tearDown(self):
        shadow_mode._shadow_state.clear()
        shadow_mode._shadow_state.update(shadow_mode._empty_state())

    def test_shadow_buy_never_mutates_actual_paper_account(self):
        app = DummyAppModule()
        original_account = deepcopy(app.account)
        with patch.object(shadow_mode, "_load_shadow_state"), patch.object(
            shadow_mode,
            "_save_shadow_state",
        ):
            shadow_mode.install_shadow_mode(app)
            shadow_mode._shadow_state["enabled"] = True
            candidate = app._score_symbol("AAPL")
            result = app._place_paper_buy(candidate)

        self.assertTrue(result["ok"])
        self.assertTrue(result["shadow"])
        self.assertFalse(result["real_order_submitted"])
        self.assertFalse(app.real_buy_called)
        self.assertEqual(app.account, original_account)
        self.assertEqual(app.positions, [])
        self.assertEqual(len(shadow_mode._shadow_state["positions"]), 1)

    def test_unvalidated_strategy_cannot_start_outside_shadow_mode(self):
        app = DummyAppModule()
        with patch.object(shadow_mode, "_load_shadow_state"), patch.object(
            shadow_mode,
            "_save_shadow_state",
        ), patch.dict(os.environ, {}, clear=True):
            shadow_mode.install_shadow_mode(app)
            result = app.start_autonomous_trader()

        self.assertFalse(app.real_start_called)
        self.assertEqual(result["last_status"], "BLOCKED_STRATEGY_EVIDENCE")
        self.assertEqual(result["last_action"], "START_REJECTED")


if __name__ == "__main__":
    unittest.main()
