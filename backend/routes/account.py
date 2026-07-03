from fastapi import APIRouter

from backend.portfolio import account, calc_equity

router = APIRouter()


@router.get("/account")
def get_account():
    account["equity"] = calc_equity()
    return account