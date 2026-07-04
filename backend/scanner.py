from datetime import datetime

from backend.ai_engine import analyze_symbol
from backend.trade_planner import build_trade_plan
from backend.universe import SYMBOLS
from backend.market import candles


def recommendation_rank(recommendation):
    ranks = {
        "STRONG BUY": 5,
        "BUY WATCH": 4,
        "NEUTRAL": 3,
        "AVOID / SELL WATCH": 2,
        "STRONG SELL": 1,
    }
    return ranks.get(recommendation, 0)


def scan_market(limit=10):
    results = []

    for symbol in SYMBOLS:
        analysis = analyze_symbol(symbol, candles.get(symbol, []))

        if analysis.get("error"):
            continue

        trade_plan = build_trade_plan(symbol, candles.get(symbol, []))

        results.append({
            "symbol": symbol,
            "recommendation": analysis["recommendation"],
            "confidence": analysis["confidence"],
            "risk_score": analysis["risk_score"],
            "score": analysis["score"],
            "market_regime": analysis["market_regime"],
            "trend": analysis["trend"],
            "buy_probability": analysis["buy_probability"],
            "sell_probability": analysis["sell_probability"],
            "trade_action": trade_plan.get("action", "NO TRADE"),
            "quality": trade_plan.get("quality", "N/A"),
            "entry": trade_plan.get("entry"),
            "stop_loss": trade_plan.get("stop_loss"),
            "take_profit_1": trade_plan.get("take_profit_1"),
            "take_profit_2": trade_plan.get("take_profit_2"),
            "summary": analysis["summary"],
        })

    results.sort(
        key=lambda x: (
            recommendation_rank(x["recommendation"]),
            x["confidence"],
            -x["risk_score"],
            x["score"],
        ),
        reverse=True,
    )

    return {
        "scan_time": datetime.utcnow().isoformat(),
        "symbols_scanned": len(SYMBOLS),
        "opportunities": results[:limit],
    }