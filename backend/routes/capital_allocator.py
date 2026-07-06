from fastapi import APIRouter

from backend.capital_allocator import allocate_capital

router = APIRouter()


@router.post("/capital-allocation")
def capital_allocation(trades: list[dict]):
    return allocate_capital(trades)