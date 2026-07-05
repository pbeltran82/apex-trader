from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.account import router as account_router
from backend.routes.market import router as market_router
from backend.routes.portfolio import router as portfolio_router
from backend.routes.backtester import router as backtester_router
from backend.routes.ai import router as ai_router
from backend.routes.trade_planner import router as trade_planner_router
from backend.routes.scanner import router as scanner_router
from backend.routes.portfolio_ai import router as portfolio_ai_router
from backend.routes.portfolio_coach import router as portfolio_coach_router
from backend.routes.position_advisor import router as position_advisor_router
from backend.routes.daily_plan import router as daily_plan_router
from backend.routes.execution_queue import router as execution_queue_router
from backend.routes.execution_manager import router as execution_manager_router
from backend.routes.activity import router as activity_router
from backend.routes.portfolio_live import router as portfolio_live_router
from backend.routes.trade_history import router as trade_history_router
from backend.routes.performance import router as performance_router
from backend.routes.exit import router as exit_router
from backend.routes.auto_exit import router as auto_exit_router
from backend.routes.equity_curve import router as equity_curve_router
from backend.routes.autopilot import router as autopilot_router

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
app.include_router(portfolio_ai_router,prefix="/api")
app.include_router(portfolio_coach_router,prefix="/api")
app.include_router(position_advisor_router, prefix="/api")
app.include_router(daily_plan_router, prefix="/api")
app.include_router(execution_queue_router, prefix="/api")
app.include_router(execution_manager_router, prefix="/api")
app.include_router(activity_router, prefix="/api")
app.include_router(portfolio_live_router, prefix="/api")
app.include_router(trade_history_router, prefix="/api")
app.include_router(performance_router, prefix="/api")
app.include_router(exit_router, prefix="/api")
app.include_router(auto_exit_router, prefix="/api")
app.include_router(equity_curve_router, prefix="/api")
app.include_router(autopilot_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "Kyle Trader backend running"}

    