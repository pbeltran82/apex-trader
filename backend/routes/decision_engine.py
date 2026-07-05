from fastapi import APIRouter

from backend.decision_engine import evaluate_trade

router = APIRouter()


@router.get("/decision-engine/{symbol}")
def decision_engine(
    symbol: str,
    confidence: float = 90,
    strategy: str = "Momentum",
    sector: str = "Other",
):
    return evaluate_trade(
        symbol=symbol,
        confidence=confidence,
        strategy=strategy,
        sector=sector,
    )