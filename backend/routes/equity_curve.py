from fastapi import APIRouter

from backend.performance import build_performance

router = APIRouter()

history = []


@router.get("/equity-curve")
def equity_curve():
    performance = build_performance()

    history.append(
        {
            "equity": performance["current_equity"],
            "return_pct": performance["return_pct"],
        }
    )

    return history[-100:]