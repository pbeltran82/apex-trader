from fastapi import APIRouter

from backend.portfolio_ai import analyze_portfolio

router = APIRouter()


@router.get("/portfolio-analysis")
def portfolio_analysis():
    return analyze_portfolio()