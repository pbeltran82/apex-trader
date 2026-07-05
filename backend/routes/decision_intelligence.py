from fastapi import APIRouter

from backend.decision_intelligence import adjust_trade_confidence

router = APIRouter()


@router.get("/decision-intelligence/{symbol}")
def decision_intelligence(
    symbol: str,
    confidence: float = 90,
    strategy: str = "Momentum",
    sector: str = "Other",
):
    return {
        "symbol": symbol.upper(),
        **adjust_trade_confidence(
            base_confidence=confidence,
            strategy=strategy,
            sector=sector,
        ),
    }