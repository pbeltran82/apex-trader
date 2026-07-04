from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.account import router as account_router
from backend.routes.market import router as market_router
from backend.routes.portfolio import router as portfolio_router
from backend.routes.backtester import router as backtester_router
from backend.routes.ai import router as ai_router
from backend.routes.trade_planner import router as trade_planner_router
from backend.routes.scanner import router as scanner_router

app = FastAPI(title="Kyle Trader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(backtester_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(trade_planner_router, prefix="/api")
app.include_router(scanner_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "Kyle Trader backend running"}