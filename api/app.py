import core.env  # MUST BE FIRST LINE

from fastapi import FastAPI
from services.trading_service import TradingService

app = FastAPI()

service = None


@app.get("/") 
def root():
    return {
        "status": "ok",
        "service": "Apex Trader API",
        "docs": "/docs"
    }


@app.on_event("startup")
def startup():
    global service
    service = TradingService()