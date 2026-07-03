from dotenv import load_dotenv
from pathlib import Path
import os

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

# Load environment variables
load_dotenv(Path("/workspaces/apex-trader/.env"), override=True)


class AlpacaBroker:
    def __init__(self):
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY")

        self.client = TradingClient(
            api_key,
            secret_key,
            paper=True
        )

        self.data_client = StockHistoricalDataClient(
            api_key,
            secret_key
        )

    # -----------------------
    # Account
    # -----------------------

    def get_account(self):
        return self.client.get_account()

    def get_positions(self):
        return self.client.get_all_positions()

    # -----------------------
    # Orders
    # -----------------------

    def submit_order(self, symbol: str, qty: float, side: str):
        order = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )

        return self.client.submit_order(order)

    # -----------------------
    # Market Data
    # -----------------------

    def get_latest_trade(self, symbol: str):
        symbol = symbol.upper()

        request = StockLatestTradeRequest(
            symbol_or_symbols=symbol
        )

        data = self.data_client.get_stock_latest_trade(request)

        return data[symbol]

    def get_latest_price(self, symbol: str) -> float:
        trade = self.get_latest_trade(symbol)
        return float(trade.price)

    # -----------------------
    # Health
    # -----------------------

    def ping(self):
        """
        Verifies connectivity to Alpaca.
        """
        account = self.get_account()

        return {
            "status": "connected",
            "account_status": str(account.status),
            "equity": float(account.equity),
            "cash": float(account.cash),
        }