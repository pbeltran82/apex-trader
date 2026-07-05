from fastapi import APIRouter

from backend.performance import build_performance

router = APIRouter()


@router.get("/performance")
def performance():
    return build_performance()