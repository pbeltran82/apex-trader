from fastapi import APIRouter

from backend.health_score import build_health_score

router = APIRouter()


@router.get("/health-score")
def health_score():
    return build_health_score()