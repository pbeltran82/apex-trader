from backend.decision_intelligence import adjust_trade_confidence
from backend.volatility_intelligence import analyze_volatility
from backend.adaptive_intelligence import get_adaptive_state
from backend.market_regime import get_market_regime
from backend.sector_rotation import get_sector_rotation_adjustment
from backend.correlation_engine import analyze_correlation_risk
from backend.portfolio_live import build_portfolio_live


def build_decision_context(
    symbol,
    confidence,
    strategy,
    sector,
):
    confidence = float(confidence)

    portfolio = build_portfolio_live()

    return {
        "symbol": symbol.upper(),
        "confidence": confidence,
        "strategy": strategy,
        "sector": sector,
        "portfolio": portfolio,
        "decision_intelligence": adjust_trade_confidence(
            confidence,
            strategy=strategy,
            sector=sector,
        ),
        "volatility": analyze_volatility(symbol),
        "adaptive": get_adaptive_state(),
        "market_regime": get_market_regime(),
        "sector_rotation": get_sector_rotation_adjustment(sector),
        "correlation": analyze_correlation_risk(symbol),
    }