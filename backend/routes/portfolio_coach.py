from fastapi import APIRouter

from backend.portfolio_coach import build_portfolio_coach

router = APIRouter()


@router.get("/portfolio-coach")
def portfolio_coach():
    return build_portfolio_coach()