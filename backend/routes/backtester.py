from fastapi import APIRouter

router = APIRouter()


@router.get("/backtest-strategies")
def backtest_strategies():
    return [
        {"id": "ema", "name": "EMA 9 / EMA 20 Crossover"},
    ]


@router.get("/backtest/{symbol}")
def backtest(symbol: str, strategy: str = "ema"):
    return {
        "symbol": symbol.upper(),
        "strategy": "EMA 9 / EMA 20 Crossover",
        "starting_equity": 10000,
        "ending_equity": 10000,
        "total_pnl": 0,
        "total_return": 0,
        "win_rate": 0,
        "trades_count": 0,
        "wins": 0,
        "losses": 0,
        "profit_factor": 0,
        "sharpe": 0,
        "max_drawdown": 0,
        "trades": [],
        "equity_curve": [],
        "ai_summary": {
            "verdict": "Neutral",
            "confidence": 50,
            "summary": "Backtester route is connected. Strategy logic will be reconnected next.",
            "recommendations": [
                "Confirm route is working.",
                "Reconnect full strategy engine.",
            ],
        },
    }