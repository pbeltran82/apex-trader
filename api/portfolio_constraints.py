from __future__ import annotations

from copy import deepcopy
import os
from typing import Any, Dict

from api.intelligence import SECTOR_MAP


CORRELATION_GROUPS = {
    "Mega Cap Technology": {"AAPL", "MSFT", "NVDA"},
    "Consumer Growth": {"AMZN", "TSLA"},
}


def _limit(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        return max(0.10, min(0.75, float(raw)))
    except ValueError:
        return default


def correlation_group(symbol: str) -> str:
    symbol = str(symbol).strip().upper()
    for name, symbols in CORRELATION_GROUPS.items():
        if symbol in symbols:
            return name
    return "Unclassified"


def _estimated_notional(app_module: Any, candidate: Dict[str, Any]) -> float:
    price = float(candidate.get("price") or 0)
    if price <= 0:
        return 0.0

    equity = max(float(app_module.account.get("equity", 0)), 1.0)
    buying_power = max(float(app_module.account.get("buying_power", 0)), 0.0)
    risk_model = candidate.get("risk_model", {})
    risk_pct = float(risk_model.get("risk_per_trade_pct") or 0.005)
    stop_pct = float(risk_model.get("stop_loss_pct") or app_module.config["stop_loss_pct"])
    risk_budget = equity * risk_pct
    per_share_risk = price * stop_pct

    qty_by_risk = int(risk_budget // per_share_risk) if per_share_risk > 0 else 0
    qty_by_notional = int(float(app_module.config["max_position_value"]) // price)
    qty_by_cash = int(buying_power // price)
    qty = min(qty_by_risk, qty_by_notional, qty_by_cash)
    return round(max(0, qty) * price, 2)


def evaluate_constraints(app_module: Any, candidate: Dict[str, Any]) -> Dict[str, Any]:
    symbol = app_module._normalize_symbol(candidate["symbol"])
    equity = max(float(app_module.account.get("equity", 0)), 1.0)
    projected_notional = _estimated_notional(app_module, candidate)
    sector = SECTOR_MAP.get(symbol, "Unknown")
    group = correlation_group(symbol)

    sector_value = sum(
        float(position.get("market_value", 0))
        for position in app_module.positions
        if SECTOR_MAP.get(position.get("symbol"), "Unknown") == sector
    )
    group_value = sum(
        float(position.get("market_value", 0))
        for position in app_module.positions
        if correlation_group(position.get("symbol", "")) == group
    )

    sector_limit = _limit("KYLE_MAX_SECTOR_EXPOSURE_PCT", 0.30)
    group_limit = _limit("KYLE_MAX_CORRELATED_GROUP_EXPOSURE_PCT", 0.30)
    projected_sector_pct = (sector_value + projected_notional) / equity
    projected_group_pct = (group_value + projected_notional) / equity

    checks = {
        "safe_position_size_available": projected_notional > 0,
        "projected_sector_exposure_within_limit": projected_sector_pct <= sector_limit,
        "projected_correlation_exposure_within_limit": (
            True if group == "Unclassified" else projected_group_pct <= group_limit
        ),
    }
    passed = all(checks.values())

    return {
        "passed": passed,
        "symbol": symbol,
        "sector": sector,
        "correlation_group": group,
        "estimated_new_position_value": projected_notional,
        "current_sector_exposure_pct": round((sector_value / equity) * 100, 2),
        "projected_sector_exposure_pct": round(projected_sector_pct * 100, 2),
        "sector_limit_pct": round(sector_limit * 100, 2),
        "current_group_exposure_pct": round((group_value / equity) * 100, 2),
        "projected_group_exposure_pct": round(projected_group_pct * 100, 2),
        "group_limit_pct": round(group_limit * 100, 2),
        "checks": checks,
    }


def install_portfolio_constraints(app_module: Any) -> None:
    if getattr(app_module, "_portfolio_constraints_installed", False):
        return

    original_score = app_module._score_symbol
    original_buy = app_module._place_paper_buy

    def constrained_score(symbol: str) -> Dict[str, Any]:
        candidate = original_score(symbol)
        if candidate.get("action") == "HOLD" or not candidate.get("technical", {}).get("ok"):
            return candidate

        constraints = evaluate_constraints(app_module, candidate)
        hardened = deepcopy(candidate)
        hardened["portfolio_constraints"] = constraints
        hardened.setdefault("hard_filters", {})
        hardened["hard_filters"].update(constraints["checks"])

        if not constraints["passed"]:
            hardened["approved"] = False
            hardened["action"] = "WATCH" if hardened.get("score", 0) >= 55 else "PASS"
            failed = [name for name, passed in constraints["checks"].items() if not passed]
            hardened["reason"] = (
                f"{hardened.get('reason', '')} Portfolio constraints blocked entry: "
                + ", ".join(failed)
                + "."
            ).strip()
        return hardened

    def constrained_buy(candidate: Dict[str, Any]) -> Dict[str, Any]:
        constraints = evaluate_constraints(app_module, candidate)
        if not constraints["passed"]:
            return {
                "ok": False,
                "message": "Portfolio exposure constraints rejected the trade.",
                "constraints": constraints,
            }
        return original_buy(candidate)

    app_module._score_symbol = constrained_score
    app_module._place_paper_buy = constrained_buy
    app_module._portfolio_constraints_installed = True

    @app_module.app.get("/api/portfolio/constraints/{symbol}")
    def portfolio_constraint_status(symbol: str):
        normalized = app_module._normalize_symbol(symbol)
        if normalized not in app_module.prices:
            return {"ok": False, "message": f"{normalized} is not in Kyle's price universe."}
        candidate = original_score(normalized)
        return evaluate_constraints(app_module, candidate)
