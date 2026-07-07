from fastapi import APIRouter

from backend.operations_dashboard import (
    build_operations_dashboard,
)

router = APIRouter()


@router.get("/operations-dashboard")
def operations_dashboard():

    return build_operations_dashboard()