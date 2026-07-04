from fastapi import APIRouter

from backend.portfolio_live import build_portfolio_live

router = APIRouter()


@router.get("/portfolio-live")
def portfolio_live():
    return build_portfolio_live()