from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.account import router as account_router
from backend.routes.market import router as market_router
from backend.routes.market_data import router as market_data_router
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
from backend.routes.autopilot import router as autopilot_router
from backend.routes.equity_curve import router as equity_curve_router
from backend.routes.risk_governor import router as risk_governor_router
from backend.routes.autopilot_scheduler import router as autopilot_scheduler_router
from backend.routes.trade_intelligence import router as trade_intelligence_router
from backend.routes.decision_intelligence import router as decision_intelligence_router
from backend.routes.decision_engine import router as decision_engine_router
from backend.database import initialize_database
from backend.routes.exit_manager import router as exit_manager_router
from backend.position_monitor import (
    start_position_monitor,
    stop_position_monitor,
)
from backend.routes.daily_scheduler import router as daily_scheduler_router
from backend.routes.autopilot_orchestrator import router as autopilot_orchestrator_router
from backend.routes.mission_control import router as mission_control_router
from backend.routes.ceo_briefing import router as ceo_briefing_router
from backend.routes.event_log import router as event_log_router
from backend.routes.alerts import router as alerts_router
from backend.routes.health_score import router as health_score_router
from backend.routes.executive_dashboard import (
    router as executive_dashboard_router,
)
from backend.routes.market_regime import router as market_regime_router
from backend.routes.sector_rotation import router as sector_rotation_router
from backend.routes.correlation_engine import router as correlation_engine_router
from backend.routes.volatility_intelligence import (
    router as volatility_intelligence_router,
)
from backend.routes.capital_allocator import (
    router as capital_allocator_router,
)
from backend.routes.portfolio_constraints import (
    router as portfolio_constraints_router,
)
from backend.routes.risk_engine import (
    router as risk_engine_router,
)
from backend.routes.emergency_stop import router as emergency_stop_router
from backend.routes.drawdown_guard import router as drawdown_guard_router
from backend.routes.broker_health import (
    router as broker_health_router,
)
from backend.routes.reconciliation import (
    router as reconciliation_router,
)
from backend.routes.health_monitor import (
    router as health_monitor_router,
)
from backend.routes.operations_dashboard import (
    router as operations_dashboard_router,
)
from backend.routes.readiness_report import (
    router as readiness_report_router,
)
from backend.routes.burn_in import router as burn_in_router


app = FastAPI(title="Kyle Trader API")



initialize_database()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(market_data_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(backtester_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(trade_planner_router, prefix="/api")
app.include_router(scanner_router, prefix="/api")
app.include_router(portfolio_ai_router, prefix="/api")
app.include_router(portfolio_coach_router, prefix="/api")
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
app.include_router(autopilot_router, prefix="/api")
app.include_router(equity_curve_router, prefix="/api")
app.include_router(risk_governor_router, prefix="/api")
app.include_router(autopilot_scheduler_router, prefix="/api")
app.include_router(trade_intelligence_router, prefix="/api")
app.include_router(decision_intelligence_router, prefix="/api")
app.include_router(decision_engine_router, prefix="/api")
app.include_router(exit_manager_router, prefix="/api")
app.include_router(autopilot_orchestrator_router, prefix="/api")
app.include_router(mission_control_router, prefix="/api")
app.include_router(ceo_briefing_router, prefix="/api")
app.include_router(event_log_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(health_score_router, prefix="/api")
app.include_router(market_regime_router, prefix="/api")
app.include_router(sector_rotation_router, prefix="/api")
app.include_router(correlation_engine_router, prefix="/api")
app.include_router(volatility_intelligence_router, prefix="/api")
app.include_router(emergency_stop_router, prefix="/api")
app.include_router(drawdown_guard_router, prefix="/api")
app.include_router(
    broker_health_router,
    prefix="/api",
)
app.include_router(
    health_monitor_router,
    prefix="/api",
)
app.include_router(
    operations_dashboard_router,
    prefix="/api",
)
app.include_router(
    readiness_report_router,
    prefix="/api",
)
app.include_router(burn_in_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "Kyle Trader backend running"}

@app.on_event("startup")
async def startup_event():
    print("Starting Kyle services...")
    start_position_monitor()


@app.on_event("shutdown")
async def shutdown_event():
    print("Stopping Kyle services...")
    stop_position_monitor()    

app.include_router(
    daily_scheduler_router,
    prefix="/api",
) 

app.include_router(
    executive_dashboard_router,
    prefix="/api",
)

app.include_router(
    capital_allocator_router,
    prefix="/api",
)

app.include_router(
    portfolio_constraints_router,
    prefix="/api",
)

app.include_router(
    risk_engine_router,
    prefix="/api",
)

app.include_router(
    reconciliation_router,
    prefix="/api",
)
