from backend.decision_intelligence import adjust_trade_confidence
from backend.adaptive_intelligence import get_adaptive_state
from backend.market_regime import get_market_regime
from backend.sector_rotation import get_sector_rotation_adjustment
from backend.portfolio_live import build_portfolio_live


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


def get_portfolio_context():
    portfolio = build_portfolio_live()

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
    confidence = float(confidence)

    intelligence = adjust_trade_confidence(
        confidence,
        strategy=strategy,
        sector=sector,
    )

    adjusted_confidence = intelligence["adjusted_confidence"]

    portfolio_context = get_portfolio_context()

    cash_pct = portfolio_context["cash_pct"]
    exposure_pct = portfolio_context["exposure_pct"]
    open_positions = portfolio_context["open_positions"]

    risk_adjustment, risk_reasons = get_risk_adjustment(
        cash_pct,
        exposure_pct,
        open_positions,
    )

    adaptive = get_adaptive_state()
    market_regime = get_market_regime()
    sector_rotation = get_sector_rotation_adjustment(sector)

    decision_score = clamp(
        adjusted_confidence
        + risk_adjustment
        + adaptive["confidence_adjustment"]
        + market_regime["confidence_adjustment"]
        + sector_rotation["confidence_adjustment"]
    )

    recommendation = get_recommendation(decision_score)

    allocation_pct = round(
        get_allocation_pct(decision_score)
        * adaptive["allocation_multiplier"]
        * market_regime["allocation_multiplier"]
        * sector_rotation["allocation_multiplier"],
        2,
    )

    reasons = [
        f"Base confidence is {round(confidence, 2)}.",
        intelligence["strategy_adjustment"]["reason"],
        intelligence["sector_adjustment"]["reason"],
        market_regime["reason"],
        sector_rotation["reason"],
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
        "symbol": symbol.upper(),
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
        "portfolio_context": {
            "cash_pct": cash_pct,
            "exposure_pct": exposure_pct,
            "open_positions": open_positions,
        },
        "adaptive_state": adaptive,
        "reasons": reasons,
        "approved": recommendation in ["SMALL_BUY", "BUY", "STRONG_BUY"],
    }