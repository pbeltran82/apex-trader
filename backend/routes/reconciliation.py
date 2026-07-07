from fastapi import APIRouter

from backend.reconciliation import (
    reconcile_positions,
)

router = APIRouter()


@router.get("/reconciliation")
def reconciliation():
    return reconcile_positions()