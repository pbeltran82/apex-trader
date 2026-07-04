from fastapi import APIRouter

from backend.position_advisor import build_position_advice

router = APIRouter()


@router.get("/position-advice/{symbol}")
def position_advice(
    symbol: str,
    risk_pct: float = 1.0,
    max_allocation_pct: float = 10.0,
):
    return build_position_advice(
        symbol=symbol,
        risk_pct=risk_pct,
        max_allocation_pct=max_allocation_pct,
    )