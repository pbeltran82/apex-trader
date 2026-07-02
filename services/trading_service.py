from broker.alpaca_broker import AlpacaBroker
from risk.risk_manager import RiskManager


class TradingService:
    def __init__(self):
        self.broker = AlpacaBroker()
        self.risk = RiskManager()

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

    def trade(self, symbol, qty, side):
        exposure = self.get_exposure()

        ok, reason = self.risk.validate(symbol, qty, side, exposure)
        if not ok:
            return {"status": "rejected", "reason": reason}

        order = self.broker.submit_order(symbol, qty, side)

        return {
            "status": "submitted",
            "order_id": str(order.id)
        }