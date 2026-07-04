from fastapi import APIRouter

from backend.scanner import scan_market

router = APIRouter()


@router.get("/scan")
def scan(limit: int = 10):
    return scan_market(limit=limit)