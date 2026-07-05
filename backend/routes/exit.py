from fastapi import APIRouter

from backend.exit_engine import evaluate_exit

router = APIRouter()


@router.get("/exit/{symbol}")
def exit_check(symbol: str):
    return evaluate_exit(symbol)