from fastapi import APIRouter

from backend.sector_rotation import get_sector_rotation

router = APIRouter()


@router.get("/sector-rotation")
def sector_rotation():
    return get_sector_rotation()