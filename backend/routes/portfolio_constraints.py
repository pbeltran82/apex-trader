from fastapi import APIRouter

from backend.portfolio_constraints import apply_constraints

router = APIRouter()


@router.post("/portfolio-constraints")
def constraints(portfolio: dict):
    return apply_constraints(portfolio)