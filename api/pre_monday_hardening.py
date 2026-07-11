from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Dict, Iterable

from api import intelligence, market_data, shadow_mode, system_readiness


REGIME_QUOTE_SYMBOLS = ("SPY", "QQQ")
DEFAULT_MAX_HISTORY_AGE_DAYS = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _max_history_age_days() -> int:
    raw = os.getenv(
        "KYLE_MAX_HISTORY_AGE_DAYS",
        str(DEFAULT_MAX_HISTORY_AGE_DAYS),
    )
    try:
        return max(3, min(30, int(raw)))
    except ValueError:
        return DEFAULT_MAX_HISTORY_AGE_DAYS


def _symbols_with_regime(symbols: Iterable[str]) -> set[str]:
    normalized = {
        str(symbol).strip().upper()
        for symbol in symbols
        if str(symbol).strip()
    }
    normalized.update(REGIME_QUOTE_SYMBOLS)
    return normalized


def _history_payload_with_freshness(payload: Dict[str, Any]) -> Dict[str, Any]:
    hardened = deepcopy(payload)
    bars = list(hardened.get("bars") or [])
    maximum_age_days = _max_history_age_days()
    last_timestamp = bars[-1].get("timestamp") if bars else None
    observed = intelligence._parse_timestamp(last_timestamp)

    age_seconds = None
    age_days = None
    if observed is not None:
        age_seconds = max(
            0.0,
            (datetime.now(timezone.utc) - observed).total_seconds(),
        )
        age_days = age_seconds / 86_400

    fresh = bool(
        bars
        and observed is not None
        and age_days is not None
        and age_days <= maximum_age_days
    )
    hardened.update(
        {
            "last_completed_bar": last_timestamp,
            "last_completed_bar_age_seconds": (
                round(age_seconds, 2) if age_seconds is not None else None
            ),
            "last_completed_bar_age_days": (
                round(age_days, 4) if age_days is not None else None
            ),
            "max_history_age_days": maximum_age_days,
            "history_fresh": fresh,
        }
    )

    if not fresh:
        hardened["stale_bar_count"] = len(bars)
        hardened["bars"] = []
        hardened["bar_count"] = 0
        hardened["ok"] = False
        hardened["error"] = (
            "Latest completed daily bar is missing or older than "
            f"{maximum_age_days} calendar days; historical intelligence is blocked."
        )
    else:
        hardened["ok"] = bool(hardened.get("ok", True))
        hardened["bar_count"] = len(bars)

    return hardened


def _background_stop_pending(app_module: Any) -> bool:
    thread = getattr(app_module, "_autonomous_thread", None)
    stop_event = getattr(app_module, "_autonomous_stop_event", None)
    return bool(
        thread is not None
        and thread.is_alive()
        and stop_event is not None
        and stop_event.is_set()
    )


def _recalculate_readiness_summary(report: Dict[str, Any]) -> None:
    checks = list(report.get("checks") or [])
    operational_checks = [
        check for check in checks if check.get("name") != "strategy_evidence"
    ]
    strategy = report.get("strategy_validation") or {}
    operational_failed = [check for check in operational_checks if not check.get("passed")]
    failed = [check for check in checks if not check.get("passed")]
    operationally_ready = not operational_failed

    report["operationally_ready_for_paper_trading"] = operationally_ready
    report["ready_for_next_market_open"] = bool(
        operationally_ready and strategy.get("passed")
    )
    report["summary"] = {
        "operational_checks_passed": len(operational_checks) - len(operational_failed),
        "operational_checks_total": len(operational_checks),
        "strategy_evidence_passed": bool(strategy.get("passed")),
        "checks_passed": len(checks) - len(failed),
        "checks_total": len(checks),
        "failed_checks": [check.get("name") for check in failed],
    }


def install_pre_monday_hardening(app_module: Any) -> None:
    if getattr(app_module, "_pre_monday_hardening_installed", False):
        return

    # Emit timezone-aware UTC timestamps so browsers do not reinterpret UTC as
    # local wall-clock time.
    app_module._now = _utc_now
    shadow_mode._now = _utc_now

    original_load_bars = intelligence._load_bars

    def freshness_checked_bars(symbol: str) -> Dict[str, Any]:
        return _history_payload_with_freshness(original_load_bars(symbol))

    intelligence._load_bars = freshness_checked_bars
    # system_readiness imported the original function directly, so replace its
    # alias as well.
    system_readiness._load_bars = freshness_checked_bars
    with intelligence._cache_lock:
        intelligence._bars_cache.clear()
        intelligence._regime_cache.clear()

    original_refresh_market_prices = market_data.refresh_market_prices

    def refresh_with_regime_quotes(symbols: Iterable[str]) -> Dict[str, Any]:
        return original_refresh_market_prices(_symbols_with_regime(symbols))

    market_data.refresh_market_prices = refresh_with_regime_quotes
    # system_readiness also imported this function directly.
    system_readiness.refresh_market_prices = refresh_with_regime_quotes

    original_build_readiness = system_readiness.build_readiness_report

    def hardened_readiness(app: Any) -> Dict[str, Any]:
        report = original_build_readiness(app)
        expected_quote_count = len(_symbols_with_regime(app.watchlist))

        for check in report.get("checks", []):
            if check.get("name") == "authenticated_quote_coverage":
                details = dict(check.get("details") or {})
                authenticated = int(details.get("authenticated", 0))
                passed = authenticated == expected_quote_count
                details["expected"] = expected_quote_count
                details["required_symbols"] = sorted(
                    _symbols_with_regime(app.watchlist)
                )
                check["details"] = details
                check["passed"] = passed
                check["message"] = (
                    "Every watchlist and regime symbol has an authenticated Alpaca quote."
                    if passed
                    else "One or more watchlist or regime symbols lack an authenticated Alpaca quote."
                )
            elif check.get("name") == "historical_bar_coverage":
                enriched = []
                for row in check.get("details") or []:
                    payload = freshness_checked_bars(str(row.get("symbol", "")))
                    updated = dict(row)
                    updated.update(
                        {
                            "last_completed_bar": payload.get("last_completed_bar"),
                            "last_completed_bar_age_days": payload.get(
                                "last_completed_bar_age_days"
                            ),
                            "max_history_age_days": payload.get(
                                "max_history_age_days"
                            ),
                            "history_fresh": payload.get("history_fresh", False),
                        }
                    )
                    enriched.append(updated)
                check["details"] = enriched

        report["hardening"] = {
            "history_freshness_enforced": True,
            "max_history_age_days": _max_history_age_days(),
            "regime_quote_symbols": list(REGIME_QUOTE_SYMBOLS),
            "stop_before_execution_enforced": True,
            "timezone_aware_utc_events": True,
        }
        _recalculate_readiness_summary(report)
        return report

    system_readiness.build_readiness_report = hardened_readiness

    original_place_buy = app_module._place_paper_buy

    def stop_guarded_buy(candidate: Dict[str, Any]) -> Dict[str, Any]:
        if _background_stop_pending(app_module):
            shadow_enabled = bool(shadow_mode._shadow_state.get("enabled"))
            return {
                "ok": False,
                "message": "Execution cancelled because an operator stop was requested.",
                "execution_cancelled": True,
                "execution_mode": "SHADOW" if shadow_enabled else "PAPER",
                "shadow": shadow_enabled,
                "real_order_submitted": False,
            }
        return original_place_buy(candidate)

    app_module._place_paper_buy = stop_guarded_buy

    original_run_cycle = app_module.run_autonomous_cycle

    def synchronized_cycle() -> Dict[str, Any]:
        result = original_run_cycle()
        # Some wrappers update the autonomous state after the underlying cycle
        # has already constructed its response. Keep the top-level response in
        # sync with the authoritative state for the UI and audit log.
        for key in (
            "running",
            "cycles",
            "failures",
            "last_run",
            "last_error",
            "last_status",
            "last_selected_symbol",
            "last_action",
            "last_reason",
        ):
            if key in app_module._autonomous_state:
                result[key] = app_module._autonomous_state[key]
        result["pre_monday_hardening"] = {
            "history_freshness_enforced": True,
            "regime_quotes_required": list(REGIME_QUOTE_SYMBOLS),
            "stop_before_execution_enforced": True,
            "timezone_aware_utc_events": True,
        }
        return result

    app_module.run_autonomous_cycle = synchronized_cycle
    app_module._pre_monday_hardening_installed = True

    @app_module.app.get("/api/hardening/pre-monday")
    def pre_monday_hardening_status():
        return {
            "installed": True,
            "history_freshness_enforced": True,
            "max_history_age_days": _max_history_age_days(),
            "regime_quote_symbols": list(REGIME_QUOTE_SYMBOLS),
            "stop_before_execution_enforced": True,
            "timezone_aware_utc_events": True,
        }
