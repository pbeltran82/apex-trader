import unittest

from scripts.market_session_supervisor import MarketSessionSupervisor


class FakeAPI:
    def __init__(self, *, readiness=True, shadow=False, running=False):
        self.readiness = readiness
        self.shadow = shadow
        self.running = running
        self.calls = []

    def __call__(self, path, method):
        self.calls.append((method, path))
        if path == "/":
            return {"ok": True}
        if path == "/api/intelligence/readiness":
            return {
                "operationally_ready_for_paper_trading": self.readiness,
                "hardening": {
                    "history_freshness_enforced": self.readiness,
                    "stop_before_execution_enforced": self.readiness,
                },
            }
        if path == "/api/shadow" and method == "GET":
            return {"enabled": self.shadow}
        if path == "/api/shadow/enable" and method == "POST":
            self.shadow = True
            return {"ok": True, "status": {"enabled": True}}
        if path == "/api/autonomous-trader/status":
            return {"running": self.running}
        if path == "/api/autonomous-trader/start":
            self.running = True
            return {"running": True}
        if path == "/api/autonomous-trader/stop":
            self.running = False
            return {"running": False}
        raise AssertionError(f"Unexpected request: {method} {path}")


class ClockSequence:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def __call__(self):
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value


class MarketSessionSupervisorTests(unittest.TestCase):
    def test_waits_for_open_starts_once_and_stops_at_close(self):
        api = FakeAPI()
        clock = ClockSequence(
            [
                {"ok": True, "is_open": False, "next_open": "open"},
                {"ok": True, "is_open": True, "timestamp": "opened"},
                {"ok": True, "is_open": True, "timestamp": "midday"},
                {"ok": True, "is_open": False, "timestamp": "closed"},
            ]
        )
        supervisor = MarketSessionSupervisor(
            clock=clock,
            request=api,
            sleep=lambda _seconds: None,
            poll_seconds=1,
            max_wait_seconds=10,
        )

        result = supervisor.run()

        self.assertEqual(result.outcome, "COMPLETED")
        self.assertTrue(result.started_observer)
        self.assertTrue(result.stopped_observer)
        self.assertFalse(api.running)
        self.assertTrue(api.shadow)
        self.assertEqual(api.calls.count(("POST", "/api/autonomous-trader/start")), 1)
        self.assertEqual(api.calls.count(("POST", "/api/autonomous-trader/stop")), 1)

    def test_readiness_failure_never_enables_or_starts(self):
        api = FakeAPI(readiness=False)
        supervisor = MarketSessionSupervisor(
            clock=lambda: {"ok": True, "is_open": True},
            request=api,
            sleep=lambda _seconds: None,
        )

        result = supervisor.run()

        self.assertEqual(result.outcome, "SKIPPED")
        self.assertNotIn(("POST", "/api/shadow/enable"), api.calls)
        self.assertNotIn(("POST", "/api/autonomous-trader/start"), api.calls)

    def test_weekend_or_holiday_clock_times_out_without_start(self):
        api = FakeAPI()
        supervisor = MarketSessionSupervisor(
            clock=lambda: {"ok": True, "is_open": False, "next_open": "Monday"},
            request=api,
            sleep=lambda _seconds: None,
            poll_seconds=5,
            max_wait_seconds=10,
        )

        result = supervisor.run()

        self.assertEqual(result.outcome, "SKIPPED")
        self.assertNotIn(("POST", "/api/autonomous-trader/start"), api.calls)

    def test_existing_observer_is_not_started_twice(self):
        api = FakeAPI(shadow=True, running=True)
        clock = ClockSequence(
            [
                {"ok": True, "is_open": True, "timestamp": "opened"},
                {"ok": True, "is_open": False, "timestamp": "closed"},
            ]
        )
        supervisor = MarketSessionSupervisor(
            clock=clock,
            request=api,
            sleep=lambda _seconds: None,
        )

        result = supervisor.run()

        self.assertEqual(result.outcome, "COMPLETED")
        self.assertFalse(result.started_observer)
        self.assertNotIn(("POST", "/api/autonomous-trader/start"), api.calls)
        self.assertIn(("POST", "/api/autonomous-trader/stop"), api.calls)

    def test_clock_failure_during_session_stops_fail_closed(self):
        api = FakeAPI()
        clock = ClockSequence(
            [
                {"ok": True, "is_open": True, "timestamp": "opened"},
                {"ok": False, "error": "clock unavailable"},
            ]
        )
        supervisor = MarketSessionSupervisor(
            clock=clock,
            request=api,
            sleep=lambda _seconds: None,
        )

        result = supervisor.run()

        self.assertEqual(result.outcome, "STOPPED_FAIL_CLOSED")
        self.assertTrue(result.stopped_observer)
        self.assertFalse(api.running)


if __name__ == "__main__":
    unittest.main()
