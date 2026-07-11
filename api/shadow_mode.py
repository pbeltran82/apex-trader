from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional

from api.intelligence import SECTOR_MAP
from api.portfolio_constraints import correlation_group
from api.strategy_validation import strategy_validation_status


SHADOW_STATE_FILE = Path("data/shadow_state.json")
SHADOW_STARTING_EQUITY = 10_000.0
_shadow_lock = threading.RLock()


def _empty_state() -> Dict[str, Any]:
    return {
        "enabled": False,
        "enabled_at": None,
        "disabled_at": None,
        "last_reset": datetime.utcnow().isoformat(),
        "last_cycle": None,
        "cash": SHADOW_STARTING_EQUITY,
        "equity": SHADOW_STARTING_EQUITY,
        "positions": [],
        "trades": [],
        "equity_curve": [],
    }


_shadow_state: Dict[str, Any] = _empty_state()


def _now() -> str:
    return datetime.utcnow().isoformat()


def _env_float(name: str, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(os.getenv(name, str(default)))))
    except ValueError:
        return default


def _today_prefix() -> str:
    return _now()[:10]


def _load_shadow_state() -> None:
    if not SHADOW_STATE_FILE.exists():
        return
    try:
        payload = json.loads(SHADOW_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    restored = _empty_state()
    restored.update(payload)
    # Never auto-enable autonomous execution after a service restart.
    restored["enabled"] = False
    restored["disabled_at"] = _now()
    _shadow_state.clear()
    _shadow_state.update(restored)


def _save_shadow_state(app_module: Any) -> None:
    app_module._ensure_data_dir()
    temp = SHADOW_STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(_shadow_state, indent=2), encoding="utf-8")
    temp.replace(SHADOW_STATE_FILE)


def _open_shadow_position(symbol: str) -> Optional[Dict[str, Any]]:
    symbol = str(symbol).strip().upper()
    return next(
        (
            position
            for position in _shadow_state["positions"]
            if position.get("symbol") == symbol
        ),
        None,
    )


def _refresh_shadow_equity(app_module: Any, record: bool = False) -> float:
    for position in _shadow_state["positions"]:
        symbol = position["symbol"]
        current_price = float(app_module.prices.get(symbol, position["entry_price"]))
        position["current_price"] = round(current_price, 2)
        position["market_value"] = round(position["qty"] * current_price, 2)
        position["unrealized_pnl"] = round(
            (current_price - position["entry_price"]) * position["qty"],
            2,
        )
        position["unrealized_pnl_pct"] = round(
            ((current_price / position["entry_price"]) - 1) * 100,
            2,
        )

    market_value = sum(
        float(position.get("market_value", 0))
        for position in _shadow_state["positions"]
    )
    _shadow_state["equity"] = round(float(_shadow_state["cash"]) + market_value, 2)
    if record:
        _shadow_state["equity_curve"].append(
            {"timestamp": _now(), "equity": _shadow_state["equity"]}
        )
        if len(_shadow_state["equity_curve"]) > 2_000:
            del _shadow_state["equity_curve"][:-2_000]
    return float(_shadow_state["equity"])


def _record_shadow_trade(
    app_module: Any,
    symbol: str,
    side: str,
    qty: int,
    price: float,
    reason: str,
    pnl: float = 0.0,
) -> Dict[str, Any]:
    trade = {
        "id": len(_shadow_state["trades"]) + 1,
        "timestamp": _now(),
        "symbol": str(symbol).strip().upper(),
        "side": side,
        "qty": int(qty),
        "price": round(float(price), 2),
        "notional": round(int(qty) * float(price), 2),
        "reason": reason,
        "realized_pnl": round(float(pnl), 2),
        "mode": "shadow",
        "real_order_submitted": False,
    }
    _shadow_state["trades"].append(trade)
    app_module._append_decision("SHADOW_TRADE_RECORDED", {"trade": trade})
    return trade


def _shadow_sizing(app_module: Any, candidate: Dict[str, Any]) -> Dict[str, Any]:
    price = float(candidate.get("price") or 0)
    risk_model = candidate.get("risk_model", {})
    stop_pct = float(
        risk_model.get("stop_loss_pct") or app_module.config["stop_loss_pct"]
    )
    risk_pct = float(
        risk_model.get("risk_per_trade_pct")
        or _env_float("KYLE_RISK_PER_TRADE_PCT", 0.005, 0.001, 0.02)
    )
    equity = max(float(_shadow_state.get("equity", 0)), 1.0)
    cash = max(float(_shadow_state.get("cash", 0)), 0.0)
    risk_budget = equity * risk_pct
    per_share_risk = price * stop_pct
    qty_by_risk = int(risk_budget // per_share_risk) if per_share_risk > 0 else 0
    qty_by_notional = int(float(app_module.config["max_position_value"]) // price) if price > 0 else 0
    qty_by_cash = int(cash // price) if price > 0 else 0
    qty = min(qty_by_risk, qty_by_notional, qty_by_cash)
    return {
        "qty": max(0, qty),
        "qty_by_risk": qty_by_risk,
        "qty_by_notional": qty_by_notional,
        "qty_by_cash": qty_by_cash,
        "risk_budget": round(risk_budget, 2),
        "per_share_risk": round(per_share_risk, 4),
        "stop_loss_pct": stop_pct,
        "take_profit_pct": float(
            risk_model.get("take_profit_pct")
            or app_module.config["take_profit_pct"]
        ),
    }


def _shadow_constraints(app_module: Any, candidate: Dict[str, Any]) -> Dict[str, Any]:
    symbol = app_module._normalize_symbol(candidate["symbol"])
    sizing = _shadow_sizing(app_module, candidate)
    notional = round(sizing["qty"] * float(candidate.get("price") or 0), 2)
    equity = max(float(_shadow_state.get("equity", 0)), 1.0)
    sector = SECTOR_MAP.get(symbol, "Unknown")
    group = correlation_group(symbol)
    sector_value = sum(
        float(position.get("market_value", 0))
        for position in _shadow_state["positions"]
        if SECTOR_MAP.get(position.get("symbol"), "Unknown") == sector
    )
    group_value = sum(
        float(position.get("market_value", 0))
        for position in _shadow_state["positions"]
        if correlation_group(position.get("symbol", "")) == group
    )
    sector_limit = _env_float("KYLE_MAX_SECTOR_EXPOSURE_PCT", 0.30, 0.10, 0.75)
    group_limit = _env_float(
        "KYLE_MAX_CORRELATED_GROUP_EXPOSURE_PCT",
        0.30,
        0.10,
        0.75,
    )
    projected_sector = (sector_value + notional) / equity
    projected_group = (group_value + notional) / equity
    checks = {
        "safe_position_size_available": sizing["qty"] > 0,
        "maximum_shadow_positions_available": len(_shadow_state["positions"])
        < int(app_module.config["max_open_positions"]),
        "projected_sector_exposure_within_limit": projected_sector <= sector_limit,
        "projected_correlation_exposure_within_limit": (
            True if group == "Unclassified" else projected_group <= group_limit
        ),
    }
    return {
        "passed": all(checks.values()),
        "symbol": symbol,
        "sector": sector,
        "correlation_group": group,
        "estimated_new_position_value": notional,
        "current_sector_exposure_pct": round(sector_value / equity * 100, 2),
        "projected_sector_exposure_pct": round(projected_sector * 100, 2),
        "sector_limit_pct": round(sector_limit * 100, 2),
        "current_group_exposure_pct": round(group_value / equity * 100, 2),
        "projected_group_exposure_pct": round(projected_group * 100, 2),
        "group_limit_pct": round(group_limit * 100, 2),
        "checks": checks,
        "sizing": sizing,
    }


def _shadow_risk(app_module: Any) -> Dict[str, Any]:
    _refresh_shadow_equity(app_module)
    equity = max(float(_shadow_state["equity"]), 1.0)
    positions = _shadow_state["positions"]
    trades = _shadow_state["trades"]
    cash_pct = float(_shadow_state["cash"]) / equity
    largest_position_pct = (
        max(float(position.get("market_value", 0)) for position in positions) / equity
        if positions
        else 0.0
    )
    curve = _shadow_state.get("equity_curve") or [{"equity": SHADOW_STARTING_EQUITY}]
    peak = max(float(point.get("equity", 0)) for point in curve) or SHADOW_STARTING_EQUITY
    drawdown_pct = max(0.0, (peak - equity) / peak)
    today_trades = [
        trade
        for trade in trades
        if str(trade.get("timestamp", "")).startswith(_today_prefix())
    ]
    today_curve = [
        point
        for point in curve
        if str(point.get("timestamp", "")).startswith(_today_prefix())
    ]
    daily_starting_equity = (
        float(today_curve[0]["equity"]) if today_curve else SHADOW_STARTING_EQUITY
    )
    daily_loss_pct = max(0.0, (daily_starting_equity - equity) / daily_starting_equity)
    consecutive_losses = 0
    for trade in reversed(trades):
        if trade.get("side") != "SELL":
            continue
        if float(trade.get("realized_pnl", 0)) < 0:
            consecutive_losses += 1
        else:
            break
    open_risk = sum(
        max(
            0.0,
            (float(position["entry_price"]) - float(position["stop_loss"]))
            * int(position["qty"]),
        )
        for position in positions
    )
    open_risk_pct = open_risk / equity

    limits = {
        "max_drawdown_pct": 0.08,
        "max_position_concentration_pct": 0.25,
        "min_cash_pct": 0.10,
        "max_daily_trades": 12,
        "max_daily_loss_pct": _env_float("KYLE_MAX_DAILY_LOSS_PCT", 0.02, 0.001, 0.20),
        "max_consecutive_losses": int(
            _env_float("KYLE_MAX_CONSECUTIVE_LOSSES", 3, 1, 20)
        ),
        "max_open_risk_pct": _env_float("KYLE_MAX_OPEN_RISK_PCT", 0.02, 0.001, 0.20),
    }
    checks = {
        "drawdown_guard": drawdown_pct <= limits["max_drawdown_pct"],
        "position_concentration_guard": largest_position_pct
        <= limits["max_position_concentration_pct"],
        "cash_guard": cash_pct >= limits["min_cash_pct"],
        "daily_trade_limit": len(today_trades) < limits["max_daily_trades"],
        "daily_loss_guard": daily_loss_pct <= limits["max_daily_loss_pct"],
        "consecutive_loss_guard": consecutive_losses
        < limits["max_consecutive_losses"],
        "total_open_risk_guard": open_risk_pct <= limits["max_open_risk_pct"],
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "limits": limits,
        "metrics": {
            "equity": round(equity, 2),
            "cash": round(float(_shadow_state["cash"]), 2),
            "cash_pct": round(cash_pct, 4),
            "drawdown_pct": round(drawdown_pct, 4),
            "largest_position_pct": round(largest_position_pct, 4),
            "open_positions": len(positions),
            "today_trade_count": len(today_trades),
            "daily_starting_equity": round(daily_starting_equity, 2),
            "daily_loss_pct": round(daily_loss_pct, 4),
            "consecutive_losses": consecutive_losses,
            "open_risk_dollars": round(open_risk, 2),
            "open_risk_pct": round(open_risk_pct, 4),
        },
    }


def _shadow_performance(app_module: Any) -> Dict[str, Any]:
    _refresh_shadow_equity(app_module)
    sells = [trade for trade in _shadow_state["trades"] if trade["side"] == "SELL"]
    buys = [trade for trade in _shadow_state["trades"] if trade["side"] == "BUY"]
    realized = round(sum(float(trade.get("realized_pnl", 0)) for trade in sells), 2)
    unrealized = round(
        sum(float(position.get("unrealized_pnl", 0)) for position in _shadow_state["positions"]),
        2,
    )
    wins = [trade for trade in sells if float(trade.get("realized_pnl", 0)) > 0]
    losses = [trade for trade in sells if float(trade.get("realized_pnl", 0)) < 0]
    total = realized + unrealized
    return {
        "starting_equity": SHADOW_STARTING_EQUITY,
        "current_equity": _shadow_state["equity"],
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_pnl": round(total, 2),
        "return_pct": round(total / SHADOW_STARTING_EQUITY * 100, 4),
        "trade_count": len(_shadow_state["trades"]),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate_pct": round(len(wins) / len(sells) * 100, 2) if sells else 0.0,
        "open_positions": len(_shadow_state["positions"]),
    }


def shadow_status(app_module: Any) -> Dict[str, Any]:
    with _shadow_lock:
        _refresh_shadow_equity(app_module)
        return {
            "enabled": bool(_shadow_state["enabled"]),
            "execution_mode": "SHADOW" if _shadow_state["enabled"] else "DISABLED",
            "real_orders_allowed": False if _shadow_state["enabled"] else None,
            "real_order_count": 0,
            "enabled_at": _shadow_state.get("enabled_at"),
            "disabled_at": _shadow_state.get("disabled_at"),
            "last_reset": _shadow_state.get("last_reset"),
            "last_cycle": _shadow_state.get("last_cycle"),
            "cash": _shadow_state["cash"],
            "equity": _shadow_state["equity"],
            "positions": deepcopy(_shadow_state["positions"]),
            "trades": deepcopy(_shadow_state["trades"]),
            "performance": _shadow_performance(app_module),
            "risk": _shadow_risk(app_module),
            "strategy_validation": strategy_validation_status(),
            "actual_paper_account": deepcopy(app_module.account),
            "actual_paper_positions": len(app_module.positions),
            "actual_paper_trades": len(app_module.trades),
            "storage_file": str(SHADOW_STATE_FILE),
        }


def install_shadow_mode(app_module: Any) -> None:
    if getattr(app_module, "_shadow_mode_installed", False):
        return

    _load_shadow_state()
    original_score = app_module._score_symbol
    original_buy = app_module._place_paper_buy
    original_manage = app_module._manage_positions
    original_run_cycle = app_module.run_autonomous_cycle
    original_start = app_module.start_autonomous_trader

    def shadow_aware_score(symbol: str) -> Dict[str, Any]:
        candidate = original_score(symbol)
        if not _shadow_state["enabled"]:
            return candidate

        hardened = deepcopy(candidate)
        hardened["execution_mode"] = "SHADOW"
        hardened["real_order_submitted"] = False
        if _open_shadow_position(symbol):
            hardened.update(
                {
                    "action": "HOLD",
                    "approved": False,
                    "reason": "Shadow portfolio already holds this symbol; duplicate hypothetical entries are blocked.",
                }
            )
            return hardened

        constraints = _shadow_constraints(app_module, hardened)
        risk = _shadow_risk(app_module)
        hardened["portfolio_constraints"] = constraints
        hardened["shadow_risk"] = risk
        hardened.setdefault("hard_filters", {})
        hardened["hard_filters"].update(constraints["checks"])
        hardened["hard_filters"]["shadow_risk_gate_ready"] = risk["ready"]
        if not constraints["passed"] or not risk["ready"]:
            hardened["approved"] = False
            hardened["action"] = "WATCH" if hardened.get("score", 0) >= 55 else "PASS"
            blockers = [
                name
                for name, passed in hardened["hard_filters"].items()
                if not passed
            ]
            hardened["reason"] = (
                f"{hardened.get('reason', '')} Shadow controls blocked entry: "
                + ", ".join(blockers)
                + "."
            ).strip()
        return hardened

    def shadow_buy(candidate: Dict[str, Any]) -> Dict[str, Any]:
        if not _shadow_state["enabled"]:
            return original_buy(candidate)

        with _shadow_lock:
            symbol = app_module._normalize_symbol(candidate["symbol"])
            if not candidate.get("approved"):
                return {
                    "ok": False,
                    "shadow": True,
                    "real_order_submitted": False,
                    "message": "Candidate is not approved for a shadow entry.",
                }
            if _open_shadow_position(symbol):
                return {
                    "ok": False,
                    "shadow": True,
                    "real_order_submitted": False,
                    "message": f"Shadow portfolio already holds {symbol}.",
                }

            constraints = _shadow_constraints(app_module, candidate)
            risk = _shadow_risk(app_module)
            sizing = constraints["sizing"]
            if not constraints["passed"] or not risk["ready"] or sizing["qty"] <= 0:
                return {
                    "ok": False,
                    "shadow": True,
                    "real_order_submitted": False,
                    "message": "Shadow risk or portfolio constraints rejected the hypothetical entry.",
                    "constraints": constraints,
                    "risk": risk,
                }

            price = float(candidate["price"])
            qty = int(sizing["qty"])
            notional = round(qty * price, 2)
            stop_pct = float(sizing["stop_loss_pct"])
            target_pct = float(sizing["take_profit_pct"])
            initial_risk = round(qty * price * stop_pct, 2)
            position = {
                "symbol": symbol,
                "qty": qty,
                "entry_price": round(price, 2),
                "current_price": round(price, 2),
                "market_value": notional,
                "opened_at": _now(),
                "stop_loss": round(price * (1 - stop_pct), 2),
                "take_profit": round(price * (1 + target_pct), 2),
                "stop_loss_pct": round(stop_pct, 4),
                "take_profit_pct": round(target_pct, 4),
                "risk_budget": sizing["risk_budget"],
                "initial_risk": initial_risk,
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0,
                "mode": "shadow",
                "real_order_submitted": False,
                "signal_snapshot": {
                    "score": candidate.get("score"),
                    "threshold": candidate.get("threshold"),
                    "components": deepcopy(candidate.get("components", {})),
                    "hard_filters": deepcopy(candidate.get("hard_filters", {})),
                    "technical": deepcopy(candidate.get("technical", {})),
                    "market_regime": deepcopy(candidate.get("market_regime", {})),
                    "portfolio_constraints": deepcopy(constraints),
                },
            }
            _shadow_state["cash"] = round(float(_shadow_state["cash"]) - notional, 2)
            _shadow_state["positions"].append(position)
            trade = _record_shadow_trade(
                app_module,
                symbol,
                "BUY",
                qty,
                price,
                candidate.get("reason", "Shadow signal."),
            )
            _refresh_shadow_equity(app_module, record=True)
            _save_shadow_state(app_module)
            app_module._append_decision(
                "SHADOW_BUY",
                {
                    "position": position,
                    "trade": trade,
                    "real_order_submitted": False,
                },
            )
            return {
                "ok": True,
                "shadow": True,
                "execution_mode": "SHADOW",
                "real_order_submitted": False,
                "message": "Shadow buy recorded; no paper or live order was submitted.",
                "position": position,
                "trade": trade,
                "sizing": sizing,
                "constraints": constraints,
            }

    def close_shadow_position(symbol: str, reason: str) -> Dict[str, Any]:
        with _shadow_lock:
            position = _open_shadow_position(symbol)
            if not position:
                return {"ok": False, "message": f"No shadow position for {symbol}."}
            current_price = float(
                app_module.prices.get(position["symbol"], position["entry_price"])
            )
            qty = int(position["qty"])
            proceeds = round(qty * current_price, 2)
            pnl = round((current_price - float(position["entry_price"])) * qty, 2)
            _shadow_state["cash"] = round(float(_shadow_state["cash"]) + proceeds, 2)
            _shadow_state["positions"].remove(position)
            trade = _record_shadow_trade(
                app_module,
                position["symbol"],
                "SELL",
                qty,
                current_price,
                reason,
                pnl,
            )
            _refresh_shadow_equity(app_module, record=True)
            _save_shadow_state(app_module)
            app_module._append_decision(
                "SHADOW_SELL",
                {
                    "trade": trade,
                    "real_order_submitted": False,
                },
            )
            return {
                "ok": True,
                "shadow": True,
                "real_order_submitted": False,
                "trade": trade,
                "realized_pnl": pnl,
            }

    def shadow_manage() -> List[Dict[str, Any]]:
        if not _shadow_state["enabled"]:
            return original_manage()
        updates: List[Dict[str, Any]] = []
        for position in list(_shadow_state["positions"]):
            current = float(
                app_module.prices.get(position["symbol"], position["entry_price"])
            )
            if current <= float(position["stop_loss"]):
                updates.append(
                    close_shadow_position(
                        position["symbol"],
                        "Shadow position-level stop loss triggered.",
                    )
                )
            elif current >= float(position["take_profit"]):
                updates.append(
                    close_shadow_position(
                        position["symbol"],
                        "Shadow position-level take profit triggered.",
                    )
                )
        _refresh_shadow_equity(app_module, record=True)
        _save_shadow_state(app_module)
        return updates

    def guarded_cycle() -> Dict[str, Any]:
        validation = strategy_validation_status()
        if not _shadow_state["enabled"] and not validation["passed"]:
            with app_module._autonomous_lock:
                app_module._autonomous_state["cycles"] += 1
                app_module._autonomous_state["last_run"] = app_module._now()
                app_module._autonomous_state.update(
                    {
                        "last_status": "BLOCKED_STRATEGY_EVIDENCE",
                        "last_action": "NO_TRADE",
                        "last_selected_symbol": None,
                        "last_reason": validation["message"],
                    }
                )
                event = app_module._append_decision(
                    "STRATEGY_EVIDENCE_BLOCKED",
                    {"validation": validation},
                )
                app_module._save_state()
                return app_module.autonomous_status(
                    extra={"decision": event, "strategy_validation": validation}
                )

        result = original_run_cycle()
        if _shadow_state["enabled"]:
            with _shadow_lock:
                _shadow_state["last_cycle"] = _now()
                _refresh_shadow_equity(app_module, record=True)
                _save_shadow_state(app_module)
            details = result.get("details") or {}
            order_result = details.get("order_result") or {}
            if order_result.get("shadow"):
                app_module._autonomous_state.update(
                    {
                        "last_status": "SHADOW_CYCLE_COMPLETE",
                        "last_action": "SHADOW_BUY",
                        "last_reason": order_result.get("message"),
                    }
                )
            result["shadow_mode"] = shadow_status(app_module)
            app_module._append_decision(
                "SHADOW_CYCLE_SUMMARY",
                {
                    "last_status": app_module._autonomous_state.get("last_status"),
                    "last_action": app_module._autonomous_state.get("last_action"),
                    "performance": _shadow_performance(app_module),
                    "real_order_submitted": False,
                },
            )
        return result

    def guarded_start() -> Dict[str, Any]:
        validation = strategy_validation_status()
        if not _shadow_state["enabled"] and not validation["passed"]:
            app_module._autonomous_state.update(
                {
                    "running": False,
                    "last_status": "BLOCKED_STRATEGY_EVIDENCE",
                    "last_action": "START_REJECTED",
                    "last_reason": validation["message"],
                }
            )
            event = app_module._append_decision(
                "AUTONOMOUS_START_REJECTED",
                {"validation": validation, "shadow_enabled": False},
            )
            app_module._save_state()
            return app_module.autonomous_status(
                extra={"decision": event, "strategy_validation": validation}
            )
        if _shadow_state["enabled"] and app_module.positions:
            return app_module.autonomous_status(
                extra={
                    "error": "Shadow mode requires zero real paper positions.",
                    "shadow_mode": shadow_status(app_module),
                }
            )
        result = original_start()
        if _shadow_state["enabled"]:
            app_module._autonomous_state["last_reason"] = (
                "Autonomous shadow observer started; no paper or live orders can be submitted."
            )
            app_module._append_decision(
                "SHADOW_OBSERVER_STARTED",
                {"real_orders_allowed": False},
            )
            app_module._save_state()
            result = app_module.autonomous_status(
                extra={"shadow_mode": shadow_status(app_module)}
            )
        return result

    app_module._score_symbol = shadow_aware_score
    app_module._place_paper_buy = shadow_buy
    app_module._manage_positions = shadow_manage
    app_module.run_autonomous_cycle = guarded_cycle
    app_module.start_autonomous_trader = guarded_start
    app_module._shadow_mode_installed = True

    @app_module.app.get("/api/shadow")
    def get_shadow_status():
        return shadow_status(app_module)

    @app_module.app.post("/api/shadow/enable")
    def enable_shadow_mode():
        if app_module._autonomous_state.get("running"):
            return {
                "ok": False,
                "message": "Stop the autonomous trader before enabling shadow mode.",
                "status": shadow_status(app_module),
            }
        if app_module.positions:
            return {
                "ok": False,
                "message": "Liquidate or reset real paper positions before enabling shadow mode.",
                "status": shadow_status(app_module),
            }
        with _shadow_lock:
            _shadow_state["enabled"] = True
            _shadow_state["enabled_at"] = _now()
            _shadow_state["disabled_at"] = None
            _refresh_shadow_equity(app_module, record=True)
            _save_shadow_state(app_module)
        event = app_module._append_decision(
            "SHADOW_MODE_ENABLED",
            {"real_orders_allowed": False},
        )
        return {
            "ok": True,
            "message": "Shadow mode enabled. Kyle can observe and simulate, but cannot place paper or live orders.",
            "event": event,
            "status": shadow_status(app_module),
        }

    @app_module.app.post("/api/shadow/disable")
    def disable_shadow_mode():
        app_module.stop_autonomous_trader()
        with _shadow_lock:
            _shadow_state["enabled"] = False
            _shadow_state["disabled_at"] = _now()
            _save_shadow_state(app_module)
        event = app_module._append_decision(
            "SHADOW_MODE_DISABLED",
            {"real_orders_allowed": False},
        )
        return {
            "ok": True,
            "message": "Shadow mode disabled and autonomous observer stopped.",
            "event": event,
            "status": shadow_status(app_module),
        }

    @app_module.app.post("/api/shadow/reset")
    def reset_shadow_mode():
        app_module.stop_autonomous_trader()
        with _shadow_lock:
            _shadow_state.clear()
            _shadow_state.update(_empty_state())
            _save_shadow_state(app_module)
        event = app_module._append_decision(
            "SHADOW_MODE_RESET",
            {"starting_equity": SHADOW_STARTING_EQUITY},
        )
        return {
            "ok": True,
            "message": "Shadow ledger reset to $10,000 with no hypothetical positions.",
            "event": event,
            "status": shadow_status(app_module),
        }

    @app_module.app.post("/api/shadow/run")
    def run_shadow_cycle():
        if not _shadow_state["enabled"]:
            return {
                "ok": False,
                "message": "Enable shadow mode before running a shadow cycle.",
                "status": shadow_status(app_module),
            }
        return app_module.run_autonomous_cycle()

    @app_module.app.post("/api/shadow/close-all")
    def close_all_shadow_positions():
        results = [
            close_shadow_position(
                position["symbol"],
                "Manual end-of-session shadow close.",
            )
            for position in list(_shadow_state["positions"])
        ]
        return {
            "ok": True,
            "results": results,
            "status": shadow_status(app_module),
        }
