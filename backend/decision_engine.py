from backend.decision_intelligence import adjust_trade_confidence
from backend.portfolio_live import build_portfolio_live
from backend.adaptive_intelligence import get_adaptive_state


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def get_recommendation(score):
    if score >= 95:
        return "STRONG_BUY"
    if score >= 90:
        return "BUY"
    if score >= 85:
        return "SMALL_BUY"
    if score >= 80:
        return "WATCH"
    return "SKIP"


def get_allocation_pct(score):
    if score >= 95:
        return 6.0
    if score >= 90:
        return 4.0
    if score >= 85:
        return 2.0
    return 0.0


def evaluate_trade(
    symbol,
    confidence,
    strategy="Momentum",
    sector="Other",
):
    symbol = symbol.upper()
    portfolio = build_portfolio_live()

    intelligence = adjust_trade_confidence(
        base_confidence=confidence,
        strategy=strategy,
        sector=sector,
    )

    score = float(intelligence["adjusted_confidence"])
    reasons = []

    reasons.append(
        f"Base confidence is {intelligence['base_confidence']}."
    )

    reasons.append(intelligence["strategy_adjustment"]["reason"])
    reasons.append(intelligence["sector_adjustment"]["reason"])

    exposure = float(portfolio.get("exposure_pct", 0))
    cash_pct = float(portfolio.get("cash_pct", 100))
    open_positions = int(portfolio.get("open_positions", 0))

    risk_adjustment = 0

    if exposure >= 25:
        risk_adjustment -= 15
        reasons.append("Portfolio exposure is high.")
    elif exposure >= 18:
        risk_adjustment -= 8
        reasons.append("Portfolio exposure is elevated.")
    else:
        risk_adjustment += 2
        reasons.append("Portfolio exposure is healthy.")

    if cash_pct < 25:
        risk_adjustment -= 8
        reasons.append("Cash reserve is low.")
    else:
        risk_adjustment += 1
        reasons.append("Cash reserve is acceptable.")

    if open_positions >= 5:
        risk_adjustment -= 10
        reasons.append("Too many open positions.")
    elif open_positions >= 3:
        risk_adjustment -= 4
        reasons.append("Portfolio already has several open positions.")
    else:
        risk_adjustment += 1
        reasons.append("Open position count is manageable.")

    adaptive = get_adaptive_state()

    decision_score = clamp(
        score
        + risk_adjustment
        + adaptive["confidence_adjustment"]
    )

    recommendation = get_recommendation(decision_score)

    allocation_pct = round(
        get_allocation_pct(decision_score) * adaptive["allocation_multiplier"],
        2,
    )

    if recommendation == "SKIP":
        reasons.append("Decision score is too low to trade.")
    elif recommendation == "WATCH":
        reasons.append("Trade should be watched, not executed yet.")
    elif recommendation == "SMALL_BUY":
        reasons.append("Trade is acceptable but should use reduced size.")
    elif recommendation == "BUY":
        reasons.append("Trade is approved.")
    else:
        reasons.append("Trade has strong conviction.")

    reasons.append(adaptive["reason"])

    return {
        "symbol": symbol,
        "base_confidence": round(float(confidence), 2),
        "decision_score": round(decision_score, 2),
        "recommendation": recommendation,
        "recommended_allocation_pct": allocation_pct,
        "strategy": strategy,
        "sector": sector,
        "risk_adjustment": risk_adjustment,
        "decision_intelligence": intelligence,
        "portfolio_context": {
     "cash_pct": cash_pct,
    "exposure_pct": exposure,
    "open_positions": open_positions,
},
"adaptive_state": adaptive,
"reasons": reasons,
"approved": recommendation in ["STRONG_BUY", "BUY", "SMALL_BUY"],
        }