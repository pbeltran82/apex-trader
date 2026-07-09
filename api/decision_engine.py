from typing import Dict, List

from api import app as core
from api import risk_gate

SCORE_WEIGHTS = {
    "trend": 25,
    "momentum": 20,
    "volume": 15,
    "volatility": 15,
    "market_regime": 15,
    "risk_penalty": -15,
}

SECTOR_MAP = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Semiconductors",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _symbol_seed(symbol: str) -> int:
    return sum(ord(char) for char in symbol.upper())


def _component(symbol: str, offset: int, max_score: int, minimum: int = 0) -> int:
    seed = _symbol_seed(symbol) + offset
    span = max_score - minimum
    return int(minimum + (seed % (span + 1)))


def detect_market_regime() -> Dict:
    telemetry = risk_gate.risk_telemetry()
    drawdown = telemetry["metrics"]["drawdown_pct"]
    cash_pct = telemetry["metrics"]["cash_pct"]
    open_positions = telemetry["metrics"]["open_positions"]

    if drawdown >= 0.05:
        regime = "Defensive"
        score = 4
        bias = "Reduce exposure and favor capital preservation."
    elif cash_pct >= 0.65 and open_positions <= 2:
        regime = "Bullish Opportunity"
        score = 14
        bias = "Cash is available and risk budget is open."
    elif open_positions >= core.config["max_open_positions"]:
        regime = "Fully Allocated"
        score = 6
        bias = "Portfolio is near allocation limits."
    else:
        regime = "Balanced"
        score = 10
        bias = "Normal opportunity-seeking mode with risk controls active."

    return {
        "regime": regime,
        "score": score,
        "bias": bias,
        "metrics": telemetry["metrics"],
    }


def score_symbol(symbol: str) -> Dict:
    symbol = core._normalize_symbol(symbol)
    price = core.prices[symbol]
    regime = detect_market_regime()
    open_position = core._open_position(symbol)
    risk = risk_gate.risk_telemetry()

    trend = _component(symbol, 3, SCORE_WEIGHTS["trend"], 8)
    momentum = _component(symbol, 11, SCORE_WEIGHTS["momentum"], 6)
    volume = _component(symbol, 19, SCORE_WEIGHTS["volume"], 4)
    volatility = _component(symbol, 29, SCORE_WEIGHTS["volatility"], 5)
    market_regime = regime["score"]

    risk_penalty = 0
    risk_notes = []

    if open_position:
        risk_penalty -= 20
        risk_notes.append("Already holding this symbol.")

    if not risk["ready"]:
        risk_penalty -= 25
        risk_notes.append("Risk gate is not ready.")

    concentration = risk["metrics"]["largest_position_pct"]
    if concentration > 0.20:
        risk_penalty -= 6
        risk_notes.append("Portfolio concentration is elevated.")

    cash_pct = risk["metrics"]["cash_pct"]
    if cash_pct < 0.25:
        risk_penalty -= 8
        risk_notes.append("Cash buffer is getting tight.")

    if regime["regime"] == "Defensive":
        risk_penalty -= 8
        risk_notes.append("Market regime is defensive.")

    components = {
        "trend": trend,
        "momentum": momentum,
        "volume": volume,
        "volatility": volatility,
        "market_regime": market_regime,
        "risk_penalty": risk_penalty,
    }
    score = int(_clamp(sum(components.values()), 0, 100))

    if open_position:
        action = "HOLD"
    elif score >= core.config["min_confidence"]:
        action = "BUY"
    elif score >= 55:
        action = "WATCH"
    else:
        action = "PASS"

    strengths = []
    if trend >= 18:
        strengths.append("strong trend")
    if momentum >= 14:
        strengths.append("positive momentum")
    if volume >= 10:
        strengths.append("supportive volume")
    if volatility >= 10:
        strengths.append("healthy volatility")

    if action == "BUY":
        reason = f"{symbol} cleared the buy threshold with {', '.join(strengths) or 'balanced technical support'}."
    elif action == "WATCH":
        reason = f"{symbol} is close, but needs stronger confirmation before Kyle risks capital."
    elif action == "HOLD":
        reason = f"Kyle already holds {symbol}; no duplicate paper entry."
    else:
        reason = f"{symbol} score is below Kyle's active threshold."

    if risk_notes:
        reason = f"{reason} Risk notes: {' '.join(risk_notes)}"

    return {
        "symbol": symbol,
        "sector": SECTOR_MAP.get(symbol, "Unknown"),
        "price": price,
        "action": action,
        "score": score,
        "confidence": score,
        "approved": action == "BUY",
        "components": components,
        "reason": reason,
        "market_regime": regime,
        "risk": {
            "ready": risk["ready"],
            "cash_pct": cash_pct,
            "largest_position_pct": concentration,
            "notes": risk_notes,
        },
    }


def ranked_opportunities() -> Dict:
    candidates = sorted(
        [score_symbol(symbol) for symbol in core.watchlist if symbol in core.prices],
        key=lambda item: item["score"],
        reverse=True,
    )
    selected = next((candidate for candidate in candidates if candidate["approved"]), None)
    return {
        "market_regime": detect_market_regime(),
        "thresholds": {
            "buy": core.config["min_confidence"],
            "watch": 55,
        },
        "selected": selected,
        "candidates": candidates,
    }


def run_scored_cycle() -> Dict:
    risk = risk_gate.risk_telemetry()
    if not risk["ready"]:
        core._autonomous_state.update({
            "last_status": "BLOCKED_RISK_GATE",
            "last_action": "NO_TRADE",
            "last_selected_symbol": None,
            "last_reason": "Decision engine blocked because risk gate is not ready.",
        })
        event = core._append_decision("DECISION_ENGINE_BLOCKED", {"risk": risk})
        core._save_state()
        return {"ok": False, "message": "Blocked by risk gate.", "risk": risk, "event": event}

    with core._autonomous_lock:
        core._autonomous_state["cycles"] += 1
        core._autonomous_state["last_run"] = core._now()
        core._autonomous_state["last_error"] = None

        exit_updates = core._manage_positions()
        core._refresh_equity()

        if len(core.positions) >= core.config["max_open_positions"]:
            opportunities = ranked_opportunities()
            core._autonomous_state.update({
                "last_status": "MAX_POSITIONS",
                "last_action": "MANAGED_ONLY",
                "last_selected_symbol": None,
                "last_reason": "Maximum open positions reached; decision engine managed exits only.",
            })
            event = core._append_decision("SCORED_AUTONOMOUS_CYCLE", {
                "status": "MAX_POSITIONS",
                "action": "MANAGED_ONLY",
                "exit_updates": exit_updates,
                "opportunities": opportunities,
            })
            core._save_state()
            return core.autonomous_status(extra={"exit_updates": exit_updates, "opportunities": opportunities, "decision": event})

        opportunities = ranked_opportunities()
        selected = opportunities["selected"]

        if not selected:
            core._autonomous_state.update({
                "last_status": "NO_CANDIDATE",
                "last_action": "NO_TRADE",
                "last_selected_symbol": None,
                "last_reason": "No scored candidate cleared the buy threshold.",
            })
            event = core._append_decision("SCORED_AUTONOMOUS_CYCLE", {
                "status": "NO_CANDIDATE",
                "action": "NO_TRADE",
                "exit_updates": exit_updates,
                "opportunities": opportunities,
            })
            core._save_state()
            return core.autonomous_status(extra={"exit_updates": exit_updates, "opportunities": opportunities, "decision": event})

        order_result = core._place_paper_buy(selected)
        core._autonomous_state.update({
            "last_status": "CYCLE_COMPLETE" if order_result["ok"] else "REJECTED",
            "last_action": selected["action"] if order_result["ok"] else "NO_TRADE",
            "last_selected_symbol": selected["symbol"],
            "last_reason": order_result["message"],
        })
        event = core._append_decision("SCORED_AUTONOMOUS_CYCLE", {
            "status": core._autonomous_state["last_status"],
            "action": core._autonomous_state["last_action"],
            "selected": selected,
            "order_result": order_result,
            "exit_updates": exit_updates,
            "opportunities": opportunities,
        })
        core._save_state()

        return core.autonomous_status(extra={
            "selected": selected,
            "order_result": order_result,
            "exit_updates": exit_updates,
            "opportunities": opportunities,
            "decision": event,
        })


def register_decision_engine(app):
    @app.get("/api/decision-engine/regime")
    def get_market_regime():
        return detect_market_regime()

    @app.get("/api/decision-engine/opportunities")
    def get_opportunities():
        return ranked_opportunities()

    @app.get("/api/decision-engine/score/{symbol}")
    def get_symbol_score(symbol: str):
        symbol = core._normalize_symbol(symbol)
        if symbol not in core.prices:
            return {"ok": False, "message": f"{symbol} is not in Kyle's price universe."}
        return score_symbol(symbol)

    @app.post("/api/autonomous-trader/run-scored")
    def run_scored_autonomous_cycle():
        return run_scored_cycle()
