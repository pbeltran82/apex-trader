from typing import Dict

from api import app as core
from api import risk_gate
from api.intelligence import market_regime


def score_symbol(symbol: str) -> Dict:
    symbol = core._normalize_symbol(symbol)
    if symbol not in core.prices:
        return {
            "ok": False,
            "symbol": symbol,
            "approved": False,
            "action": "PASS",
            "reason": f"{symbol} is not in Kyle's active price universe.",
        }
    return core._score_symbol(symbol)


def ranked_opportunities() -> Dict:
    candidates = sorted(
        [score_symbol(symbol) for symbol in core.watchlist if symbol in core.prices],
        key=lambda item: item.get("score", item.get("confidence", 0)),
        reverse=True,
    )
    selected = next((candidate for candidate in candidates if candidate.get("approved")), None)
    return {
        "market_regime": market_regime(core),
        "thresholds": {
            "configured_buy": core.config["min_confidence"],
            "mixed_regime_addition": 5,
        },
        "selected": selected,
        "candidates": candidates,
    }


def run_scored_cycle() -> Dict:
    # The active background loop, guarded endpoint, and scored endpoint now use
    # the same market-data, risk, intelligence, sizing, and cooldown pipeline.
    return risk_gate.guarded_cycle()


def register_decision_engine(app):
    @app.get("/api/decision-engine/regime")
    def get_market_regime():
        return market_regime(core)

    @app.get("/api/decision-engine/opportunities")
    def get_opportunities():
        return ranked_opportunities()

    @app.get("/api/decision-engine/score/{symbol}")
    def get_symbol_score(symbol: str):
        return score_symbol(symbol)

    @app.post("/api/autonomous-trader/run-scored")
    def run_scored_autonomous_cycle():
        return run_scored_cycle()
