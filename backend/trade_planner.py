from backend.ai_engine import analyze_symbol


def money(n):
    return round(float(n), 2)


def build_trade_plan(symbol, candles, account_equity=10000, risk_pct=1.0):
    analysis = analyze_symbol(symbol, candles)

    if analysis.get("error"):
        return analysis

    last_price = analysis["last_price"]
    atr = analysis["atr"]
    confidence = analysis["confidence"]
    risk_score = analysis["risk_score"]
    recommendation = analysis["recommendation"]
    blockers = analysis.get("blockers", [])

    trade_allowed = (
        "BUY" in recommendation
        and confidence >= 60
        and risk_score <= 65
        and len(blockers) <= 1
    )

    if not trade_allowed:
        return {
            "symbol": symbol.upper(),
            "action": "NO TRADE",
            "confidence": confidence,
            "risk_score": risk_score,
            "reason": "Setup rejected by trade-quality filters.",
            "blockers": blockers,
            "analysis": analysis,
        }

    entry = last_price
    stop_loss = entry - (1.5 * atr)
    take_profit_1 = entry + (2.5 * atr)
    take_profit_2 = entry + (4.5 * atr)

    risk_per_share = entry - stop_loss
    account_risk_dollars = account_equity * (risk_pct / 100)

    shares = int(account_risk_dollars / risk_per_share) if risk_per_share > 0 else 0

    rr1 = (take_profit_1 - entry) / risk_per_share if risk_per_share else 0
    rr2 = (take_profit_2 - entry) / risk_per_share if risk_per_share else 0

    quality = "MEDIUM"
    if confidence >= 75 and rr1 >= 1.5:
        quality = "HIGH"
    if confidence >= 85 and rr1 >= 2:
        quality = "EXCELLENT"

    warnings = []
    if rr1 < 1.5:
        warnings.append("First target risk/reward is below ideal threshold.")
    if shares == 0:
        warnings.append("Position size is zero under current risk settings.")

    return {
        "symbol": symbol.upper(),
        "action": "BUY",
        "quality": quality,
        "confidence": confidence,
        "risk_score": risk_score,
        "entry": money(entry),
        "stop_loss": money(stop_loss),
        "take_profit_1": money(take_profit_1),
        "take_profit_2": money(take_profit_2),
        "risk_per_share": money(risk_per_share),
        "risk_reward_1": money(rr1),
        "risk_reward_2": money(rr2),
        "suggested_shares": shares,
        "risk_pct": risk_pct,
        "account_risk_dollars": money(account_risk_dollars),
        "estimated_position_value": money(shares * entry),
        "holding_period": "Short-term swing / simulated",
        "reasons": analysis["reasoning"],
        "blockers": blockers,
        "warnings": warnings,
        "summary": (
            f"{symbol.upper()} has a {quality} BUY setup with {money(confidence)}% confidence. "
            f"Entry is near ${money(entry)}, stop is ${money(stop_loss)}, "
            f"first target is ${money(take_profit_1)}."
        ),
        "analysis": analysis,
        "disclaimer": "Simulated trade plan. Not financial advice.",
    }