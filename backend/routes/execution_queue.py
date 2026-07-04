from fastapi import APIRouter

from backend.execution_engine import (
    queue_trade,
    get_execution_queue,
    execute_trade,
    complete_trade,
)

from backend.position_advisor import build_position_advice

router = APIRouter()


@router.get("/execution-queue")
def execution_queue():
    return get_execution_queue()


@router.post("/queue/{symbol}")
def queue(symbol: str):
    advice = build_position_advice(symbol)
    return queue_trade(symbol, advice)


@router.post("/execute/{symbol}")
def execute(symbol: str):
    return execute_trade(symbol)


@router.post("/complete/{symbol}")
def complete(symbol: str):
    return complete_trade(symbol)