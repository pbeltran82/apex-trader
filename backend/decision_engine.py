from backend.decision_context import build_decision_context


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def get_recommendation(score):
    if score < 80:
        return "SKIP"
    if score < 85:
        return "WATCH"
    if score < 90:
        return "SMALL_BUY"
    if score < 95:
        return "BUY"
    return "STRONG_BUY"


def get_allocation_pct(score):
    if score < 80:
        return 0.0
    if score < 85:
        return 0.0
    if score < 90:
        return 2.0
    if score < 95:
        return 4.0
    return 6.0


def get_portfolio_context(portfolio):
    return {
        "cash_pct": portfolio.get("cash_pct", 100.0),
        "exposure_pct": portfolio.get("exposure_pct", 0.0),
        "open_positions": portfolio.get("open_positions", 0),
    }


def get_risk_adjustment(cash_pct, exposure_pct, open_positions):
    adjustment = 0
    reasons = []

    if exposure_pct < 50:
        adjustment += 2
        reasons.append("Portfolio exposure is healthy.")
    elif exposure_pct > 80:
        adjustment -= 8
        reasons.append("Portfolio exposure is high.")
    else:
        reasons.append("Portfolio exposure is acceptable.")

    if cash_pct > 20:
        adjustment += 1
        reasons.append("Cash reserve is acceptable.")
    else:
        adjustment -= 6
        reasons.append("Cash reserve is low.")

    if open_positions < 5:
        adjustment += 1
        reasons.append("Open position count is manageable.")
    else:
        adjustment -= 4
        reasons.append("Open position count is elevated.")

    return adjustment, reasons


def evaluate_trade(
    symbol,
    confidence=0,
    strategy="Momentum",
    sector="Other",
):
    context = build_decision_context(
        symbol,
        confidence,
        strategy,
        sector,
    )

    symbol = context["symbol"]
    confidence = context["confidence"]

    intelligence = context["decision_intelligence"]
    adaptive = context["adaptive"]
    market_regime = context["market_regime"]
    sector_rotation = context["sector_rotation"]
    correlation = context["correlation"]
    volatility = context.get("volatility")

    volatility_confidence_adjustment = (
        volatility.get("confidence_adjustment", 0)
        if volatility and volatility.get("can_affect_decision")
        else 0
    )

    volatility_allocation_multiplier = (
        volatility.get("allocation_multiplier", 1.0)
        if volatility and volatility.get("can_affect_decision")
        else 1.0
    )

    portfolio_context = get_portfolio_context(context["portfolio"])

    cash_pct = portfolio_context["cash_pct"]
    exposure_pct = portfolio_context["exposure_pct"]
    open_positions = portfolio_context["open_positions"]

    risk_adjustment, risk_reasons = get_risk_adjustment(
        cash_pct,
        exposure_pct,
        open_positions,
    )

    adjusted_confidence = intelligence["adjusted_confidence"]

    decision_score = clamp(
        adjusted_confidence
        + risk_adjustment
        + adaptive["confidence_adjustment"]
        + market_regime["confidence_adjustment"]
        + sector_rotation["confidence_adjustment"]
        + correlation["confidence_adjustment"]
        + volatility_confidence_adjustment
    )

    recommendation = get_recommendation(decision_score)

    allocation_pct = round(
        get_allocation_pct(decision_score)
        * adaptive["allocation_multiplier"]
        * market_regime["allocation_multiplier"]
        * sector_rotation["allocation_multiplier"]
        * correlation["allocation_multiplier"]
        * volatility_allocation_multiplier,
        2,
    )

    reasons = [
        f"Base confidence is {round(confidence, 2)}.",
        intelligence["strategy_adjustment"]["reason"],
        intelligence["sector_adjustment"]["reason"],
        market_regime["reason"],
        sector_rotation["reason"],
        correlation["reason"],
        volatility["reason"] if volatility else "No volatility data available.",
    ]

    reasons.extend(risk_reasons)

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
        "base_confidence": round(confidence, 2),
        "decision_score": round(decision_score, 2),
        "recommendation": recommendation,
        "recommended_allocation_pct": allocation_pct,
        "strategy": strategy,
        "sector": sector,
        "risk_adjustment": risk_adjustment,
        "decision_intelligence": intelligence,
        "market_regime": market_regime,
        "sector_rotation": sector_rotation,
        "correlation": correlation,
        "volatility": volatility,
        "portfolio_context": portfolio_context,
        "adaptive_state": adaptive,
        "reasons": reasons,
        "approved": recommendation in ["SMALL_BUY", "BUY", "STRONG_BUY"],
    }