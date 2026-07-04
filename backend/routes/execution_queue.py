from fastapi import APIRouter

from backend.execution_engine import (
    queue_trade_from_advice,
    get_execution_queue,
    execute_trade,
    complete_trade,
    clear_queue,
)

from backend.position_advisor import build_position_advice

router = APIRouter()


@router.get("/execution-queue")
def execution_queue():
    return get_execution_queue()


@router.post("/queue/{symbol}")
def queue(symbol: str):
    advice = build_position_advice(symbol)
    return queue_trade_from_advice(symbol, advice)


@router.post("/execute/{symbol}")
def execute(symbol: str):
    return execute_trade(symbol)


@router.post("/complete/{symbol}")
def complete(symbol: str):
    return complete_trade(symbol)


@router.delete("/execution-queue")
def clear():
    return clear_queue()