from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Optional


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cooldown_minutes() -> int:
    raw = os.getenv("KYLE_REENTRY_COOLDOWN_MINUTES", "60")
    try:
        return max(0, int(raw))
    except ValueError:
        return 60


def _latest_sell(app_module: Any, symbol: str) -> Optional[Dict[str, Any]]:
    symbol = str(symbol).strip().upper()
    return next(
        (
            trade
            for trade in reversed(app_module.trades)
            if trade.get("side") == "SELL" and trade.get("symbol") == symbol
        ),
        None,
    )


def install_runtime_hardening(app_module: Any) -> None:
    """Install low-risk runtime safeguards around the active paper engine."""

    if getattr(app_module, "_runtime_hardening_installed", False):
        return

    original_append_decision = app_module._append_decision
    original_score_symbol = app_module._score_symbol

    def immutable_append_decision(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Freeze nested state at event time so later mutations cannot rewrite
        # historical decisions in memory.
        frozen_payload = deepcopy(payload)
        event = original_append_decision(event_type, frozen_payload)
        return deepcopy(event)

    def score_symbol_with_cooldown(symbol: str) -> Dict[str, Any]:
        candidate = original_score_symbol(symbol)
        minutes = _cooldown_minutes()
        if minutes <= 0 or candidate.get("action") == "HOLD":
            return candidate

        sell = _latest_sell(app_module, candidate.get("symbol", symbol))
        if not sell:
            return candidate

        sold_at = _parse_timestamp(sell.get("timestamp"))
        if sold_at is None:
            return candidate

        expires_at = sold_at + timedelta(minutes=minutes)
        now = datetime.now(timezone.utc)
        if now >= expires_at:
            return candidate

        remaining_seconds = max(0, int((expires_at - now).total_seconds()))
        hardened = deepcopy(candidate)
        hardened.update(
            {
                "action": "WAIT",
                "approved": False,
                "reason": (
                    f"Re-entry cooldown active after the latest exit; "
                    f"{remaining_seconds} seconds remain."
                ),
                "cooldown": {
                    "active": True,
                    "minutes": minutes,
                    "sold_at": sell.get("timestamp"),
                    "expires_at": expires_at.isoformat(),
                    "remaining_seconds": remaining_seconds,
                    "last_exit_reason": sell.get("reason"),
                    "last_exit_pnl": sell.get("realized_pnl", 0.0),
                },
            }
        )
        return hardened

    app_module._append_decision = immutable_append_decision
    app_module._score_symbol = score_symbol_with_cooldown
    app_module._runtime_hardening_installed = True
