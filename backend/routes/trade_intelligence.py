from fastapi import APIRouter

from backend.trade_intelligence import (
    get_trade_intelligence_records,
    get_trade_intelligence_summary,
    clear_trade_intelligence,
)

router = APIRouter()


@router.get("/trade-intelligence")
def trade_intelligence():
    return get_trade_intelligence_summary()


@router.get("/trade-intelligence/records")
def trade_intelligence_records():
    return get_trade_intelligence_records()


@router.delete("/trade-intelligence")
def clear():
    return clear_trade_intelligence()