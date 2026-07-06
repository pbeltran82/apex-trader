from fastapi import APIRouter

from backend.executive_dashboard import build_executive_dashboard

router = APIRouter()


@router.get("/executive-dashboard")
def executive_dashboard():
    return build_executive_dashboard()