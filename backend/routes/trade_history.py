from fastapi import APIRouter

from backend.trade_history import (
    get_trade_history,
    clear_trade_history,
    get_trade_stats,
)

router = APIRouter()


@router.get("/trade-history")
def trade_history():
    return get_trade_history()


@router.delete("/trade-history")
def clear_history():
    return clear_trade_history()


@router.get("/trade-stats")
def trade_stats():
    return get_trade_stats()