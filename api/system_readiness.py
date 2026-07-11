from __future__ import annotations

from typing import Any, Dict, List

from api import risk_gate
from api.intelligence import MINIMUM_HISTORY_BARS, REGIME_SYMBOLS, _load_bars, market_regime
from api.market_data import evaluate_market_gate, refresh_market_prices
from api.security import _operator_token


def _check(name: str, passed: bool, message: str, details: Any = None) -> Dict[str, Any]:
    payload = {
        "name": name,
        "passed": bool(passed),
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    return payload


def build_readiness_report(app_module: Any) -> Dict[str, Any]:
    trade_symbols = sorted(set(app_module.watchlist))
    quote_refresh = refresh_market_prices(trade_symbols)
    market_gate = evaluate_market_gate(quote_refresh)

    authenticated_quotes = [
        row
        for row in quote_refresh.get("results", [])
        if row.get("ok") and row.get("source") == "alpaca_market_data"
    ]
    quote_coverage_ok = len(authenticated_quotes) == len(trade_symbols)

    history_symbols = sorted(set(trade_symbols).union(REGIME_SYMBOLS))
    history: List[Dict[str, Any]] = []
    for symbol in history_symbols:
        payload = _load_bars(symbol)
        history.append(
            {
                "symbol": symbol,
                "ok": bool(payload.get("ok")),
                "bar_count": int(payload.get("bar_count", 0)),
                "required_bars": MINIMUM_HISTORY_BARS,
                "source": payload.get("source"),
                "error": payload.get("error"),
            }
        )
    history_ok = all(
        row["ok"] and row["bar_count"] >= MINIMUM_HISTORY_BARS
        for row in history
    )

    regime = market_regime(app_module)
    regime_ok = regime.get("regime") != "UNKNOWN"
    risk = risk_gate.risk_telemetry()

    signal_diagnostics = []
    for symbol in trade_symbols:
        try:
            score = app_module._score_symbol(symbol)
            signal_diagnostics.append(
                {
                    "symbol": symbol,
                    "ok": bool(score.get("technical", {}).get("ok")),
                    "score": score.get("score", score.get("confidence")),
                    "action": score.get("action"),
                    "approved": bool(score.get("approved")),
                    "reason": score.get("reason"),
                }
            )
        except Exception as error:
            signal_diagnostics.append(
                {
                    "symbol": symbol,
                    "ok": False,
                    "score": None,
                    "action": "ERROR",
                    "approved": False,
                    "reason": str(error),
                }
            )
    signals_ok = all(row["ok"] for row in signal_diagnostics)

    checks = [
        _check(
            "authenticated_quote_coverage",
            quote_coverage_ok,
            "Every watchlist symbol has an authenticated Alpaca quote."
            if quote_coverage_ok
            else "One or more watchlist symbols lack an authenticated Alpaca quote.",
            {
                "expected": len(trade_symbols),
                "authenticated": len(authenticated_quotes),
            },
        ),
        _check(
            "historical_bar_coverage",
            history_ok,
            "Every trade and regime symbol has enough completed daily bars."
            if history_ok
            else "Historical-bar coverage is incomplete.",
            history,
        ),
        _check(
            "real_signal_engine",
            signals_ok,
            "Every watchlist symbol produced a real-data technical snapshot."
            if signals_ok
            else "One or more symbols failed real signal generation.",
            signal_diagnostics,
        ),
        _check(
            "market_regime",
            regime_ok,
            "SPY/QQQ regime intelligence is available."
            if regime_ok
            else "SPY/QQQ regime intelligence is unavailable.",
            regime,
        ),
        _check(
            "portfolio_risk_gate",
            risk.get("ready", False),
            "Portfolio risk limits currently pass."
            if risk.get("ready")
            else "Portfolio risk limits currently block new entries.",
            risk,
        ),
        _check(
            "operator_security",
            _operator_token() is not None,
            "Remote control requires a configured operator token."
            if _operator_token() is not None
            else "KYLE_OPERATOR_TOKEN is not configured; remote mutations are disabled.",
        ),
        _check(
            "runtime_hardening",
            bool(getattr(app_module, "_runtime_hardening_installed", False)),
            "Immutable decisions and re-entry cooldown are installed.",
        ),
        _check(
            "risk_enforcement",
            bool(getattr(app_module, "_risk_enforcement_installed", False)),
            "Risk enforcement is installed in the autonomous loop.",
        ),
        _check(
            "market_data_gate",
            bool(getattr(app_module, "_market_data_installed", False)),
            "Market clock and quote-freshness gating are installed.",
        ),
    ]

    failed = [check for check in checks if not check["passed"]]
    market_closed_normally = market_gate.get("status") == "MARKET_CLOSED"
    ready = not failed

    return {
        "ready_for_next_market_open": ready,
        "market_closed_normally": market_closed_normally,
        "market_gate": market_gate,
        "summary": {
            "checks_passed": len(checks) - len(failed),
            "checks_total": len(checks),
            "failed_checks": [check["name"] for check in failed],
        },
        "checks": checks,
        "paper_only": True,
    }


def install_system_readiness(app_module: Any) -> None:
    if getattr(app_module, "_system_readiness_installed", False):
        return

    app_module._system_readiness_installed = True

    @app_module.app.get("/api/intelligence/readiness")
    def intelligence_readiness():
        return build_readiness_report(app_module)
