import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from api import historical_data, research


def build_bars(count=260, start_price=100.0, step=0.2):
    start = datetime.now(timezone.utc) - timedelta(days=count + 20)
    bars = []
    previous = start_price
    for index in range(count):
        close = start_price + index * step
        bars.append(
            {
                "timestamp": (start + timedelta(days=index)).isoformat(),
                "open": previous,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000 + index * 1_000,
                "trade_count": 100,
                "vwap": close,
            }
        )
        previous = close
    return bars


class HistoricalPaginationTests(unittest.TestCase):
    def test_daily_bars_follows_next_page_token_and_deduplicates(self):
        first = {
            "bars": {
                "AAPL": [
                    {"t": "2025-01-01T00:00:00Z", "o": 1, "h": 2, "l": 1, "c": 2, "v": 10},
                    {"t": "2025-01-02T00:00:00Z", "o": 2, "h": 3, "l": 2, "c": 3, "v": 11},
                ]
            },
            "next_page_token": "next-token",
        }
        second = {
            "bars": {
                "AAPL": [
                    {"t": "2025-01-02T00:00:00Z", "o": 2, "h": 3, "l": 2, "c": 3, "v": 11},
                    {"t": "2025-01-03T00:00:00Z", "o": 3, "h": 4, "l": 3, "c": 4, "v": 12},
                ]
            },
            "next_page_token": None,
        }
        responses = [json.dumps(first).encode(), json.dumps(second).encode()]

        with patch.object(historical_data, "_alpaca_headers", return_value={"x": "y"}), patch.object(
            historical_data,
            "_request",
            side_effect=responses,
        ) as request:
            result = historical_data.get_daily_bars("AAPL", limit=4, lookback_days=1000)

        self.assertTrue(result["ok"])
        self.assertEqual(result["bar_count"], 3)
        self.assertEqual(result["pages_fetched"], 2)
        self.assertIn("page_token=next-token", request.call_args_list[1].args[0])
        self.assertEqual(
            [bar["timestamp"] for bar in result["bars"]],
            [
                "2025-01-01T00:00:00Z",
                "2025-01-02T00:00:00Z",
                "2025-01-03T00:00:00Z",
            ],
        )


class ResearchIntegrityTests(unittest.TestCase):
    def test_four_folds_are_contiguous_and_cover_eligible_period(self):
        ranges = research._fold_ranges(1005)
        self.assertEqual(len(ranges), 4)
        self.assertEqual(ranges[0][0], research.MIN_HISTORY)
        self.assertEqual(ranges[-1][1], 1005)
        for previous, current in zip(ranges, ranges[1:]):
            self.assertEqual(previous[1], current[0])
            self.assertGreater(previous[1], previous[0])

    def test_execution_bar_close_does_not_change_prior_close_signal(self):
        bars = build_bars()
        spy = research._index_series(build_bars(start_price=200.0, step=0.1))
        qqq = research._index_series(build_bars(start_price=300.0, step=0.1))
        indexes = {"SPY": spy, "QQQ": qqq}

        original_rows = research._feature_rows(bars, indexes)
        execution_index = research.MIN_HISTORY
        original_signal_price = original_rows[execution_index]["signal_price"]

        modified = [dict(bar) for bar in bars]
        modified[execution_index]["close"] = 1_000_000.0
        modified_rows = research._feature_rows(modified, indexes)

        self.assertEqual(
            original_signal_price,
            modified_rows[execution_index]["signal_price"],
        )

    def test_research_grid_is_fixed_and_does_not_mutate_live_settings(self):
        grid = research._config_grid()
        self.assertEqual(len(grid), 216)
        self.assertTrue(all(config.threshold in {70, 80, 90} for config in grid))
        self.assertTrue(all(config.reward_risk in {1.5, 2.0, 3.0} for config in grid))


if __name__ == "__main__":
    unittest.main()
