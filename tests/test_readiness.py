import os
import unittest
from unittest.mock import patch

from api import system_readiness


class StrategyValidationTests(unittest.TestCase):
    def test_strategy_is_unvalidated_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            result = system_readiness._strategy_validation()

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "UNVALIDATED")
        self.assertFalse(result["automatic_approval"])

    def test_only_explicit_paper_burn_in_approval_passes(self):
        with patch.dict(
            os.environ,
            {"KYLE_STRATEGY_VALIDATION_STATUS": "APPROVED_FOR_PAPER_BURN_IN"},
            clear=True,
        ):
            result = system_readiness._strategy_validation()

        self.assertTrue(result["passed"])
        self.assertEqual(
            result["required_status"],
            "APPROVED_FOR_PAPER_BURN_IN",
        )

    def test_similar_but_unapproved_status_fails(self):
        with patch.dict(
            os.environ,
            {"KYLE_STRATEGY_VALIDATION_STATUS": "RESEARCH_COMPLETE"},
            clear=True,
        ):
            result = system_readiness._strategy_validation()

        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "RESEARCH_COMPLETE")


if __name__ == "__main__":
    unittest.main()
