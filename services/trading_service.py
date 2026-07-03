from broker.alpaca_broker import AlpacaBroker
from risk.risk_manager import RiskManager
from services.trade_logger import TradeLogger


class TradingService:
    """
    Coordinates trading.

    API
      ↓
    TradingService
      ↓
    RiskManager
      ↓
    AlpacaBroker
      ↓
    TradeLogger
    """

    def __init__(self):
        self.broker = AlpacaBroker()
        self.risk = RiskManager()
        self.logger = TradeLogger()

    # -----------------------
    # Portfolio
    # -----------------------

    def get_exposure(self):
        account = self.broker.get_account()
        positions = self.broker.get_positions()

        equity = float(account.equity)
        invested = sum(float(p.market_value) for p in positions)

        return {
            "cash": float(account.cash),
            "equity": equity,
            "invested": invested,
            "open_count": len(positions),
            "invested_pct": invested / equity if equity else 0,
        }

    # -----------------------
    # Trading
    # -----------------------

    def trade(self, symbol, qty, side):

        exposure = self.get_exposure()

        approved, reason = self.risk.validate(
            symbol,
            qty,
            side,
            exposure,
        )

        if not approved:

            self.logger.log(
                symbol=symbol,
                side=side,
                qty=qty,
                status="rejected",
                reason=reason,
            )

            return {
                "status": "rejected",
                "reason": reason,
            }

        try:

            order = self.broker.submit_order(
                symbol,
                qty,
                side,
            )

            self.logger.log(
                symbol=symbol,
                side=side,
                qty=qty,
                status="submitted",
                reason="Approved",
                order_id=str(order.id),
            )

            return {
                "status": "submitted",
                "order_id": str(order.id),
            }

        except Exception as e:

            self.logger.log(
                symbol=symbol,
                side=side,
                qty=qty,
                status="error",
                reason=str(e),
            )

            raise