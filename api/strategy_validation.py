from __future__ import annotations

import os
from typing import Any, Dict


APPROVED_STRATEGY_STATUS = "APPROVED_FOR_PAPER_BURN_IN"


def strategy_validation_status() -> Dict[str, Any]:
    status = os.getenv("KYLE_STRATEGY_VALIDATION_STATUS", "UNVALIDATED").strip().upper()
    approved = status == APPROVED_STRATEGY_STATUS
    return {
        "passed": approved,
        "status": status,
        "required_status": APPROVED_STRATEGY_STATUS,
        "message": (
            "The active strategy is approved for controlled paper burn-in."
            if approved
            else "The active strategy has not passed evidence review; autonomous entries must remain disabled."
        ),
        "automatic_approval": False,
    }
