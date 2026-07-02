class RiskManager:
    MAX_ORDER_QTY = 10
    MAX_OPEN_POSITIONS = 10
    MAX_POSITION_PCT = 0.20
    MAX_INVESTED_PCT = 0.90
    MIN_CASH_BUFFER = 100

    def validate(self, symbol, qty, side, exposure):
        if qty > self.MAX_ORDER_QTY:
            return False, "Order too large"

        if side == "buy":
            if exposure["cash"] < self.MIN_CASH_BUFFER:
                return False, "Low cash buffer"

            if exposure["open_count"] >= self.MAX_OPEN_POSITIONS:
                return False, "Too many positions"

            if exposure["invested_pct"] > self.MAX_INVESTED_PCT:
                return False, "Over invested"

        return True, "OK"