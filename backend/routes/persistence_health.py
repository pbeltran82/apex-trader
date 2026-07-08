from fastapi import APIRouter

from backend.persistence_health import build_persistence_health

router = APIRouter()


@router.get("/persistence-health")
def persistence_health():
    return build_persistence_health()
