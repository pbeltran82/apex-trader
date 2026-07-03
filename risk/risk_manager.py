class RiskManager:
    """
    Centralized risk engine.

    Every trade must pass through this class before reaching the broker.
    """

    # -----------------------
    # Risk Limits
    # -----------------------

    MAX_ORDER_QTY = 10
    MIN_CASH_BUFFER = 100.00
    MAX_OPEN_POSITIONS = 10
    MAX_INVESTED_PCT = 0.90

    # Optional whitelist.
    # Set to None to allow everything.
    ALLOWED_SYMBOLS = None
    # Example:
    # ALLOWED_SYMBOLS = ["AAPL", "MSFT", "SPY", "TSLA"]

    def validate(self, symbol, qty, side, exposure):
        symbol = symbol.upper()

        # -----------------------
        # Basic validation
        # -----------------------

        if side.lower() not in ("buy", "sell"):
            return False, "Side must be 'buy' or 'sell'"

        if qty <= 0:
            return False, "Quantity must be greater than zero"

        if qty > self.MAX_ORDER_QTY:
            return (
                False,
                f"Maximum order size is {self.MAX_ORDER_QTY} shares"
            )

        # -----------------------
        # Symbol whitelist
        # -----------------------

        if (
            self.ALLOWED_SYMBOLS is not None
            and symbol not in self.ALLOWED_SYMBOLS
        ):
            return (
                False,
                f"{symbol} is not an approved trading symbol"
            )

        # -----------------------
        # Sell orders
        # -----------------------

        # Allow sells immediately.
        # (Later we'll verify position ownership.)
        if side.lower() == "sell":
            return True, "Approved"

        # -----------------------
        # Buy-side checks
        # -----------------------

        if exposure["cash"] < self.MIN_CASH_BUFFER:
            return (
                False,
                f"Cash below minimum buffer (${self.MIN_CASH_BUFFER})"
            )

        if exposure["open_count"] >= self.MAX_OPEN_POSITIONS:
            return (
                False,
                "Maximum number of open positions reached"
            )

        if exposure["invested_pct"] >= self.MAX_INVESTED_PCT:
            return (
                False,
                "Portfolio is already fully invested"
            )

        # Passed all checks
        return True, "Approved"