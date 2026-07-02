from dotenv import load_dotenv
import os
from pathlib import Path

env_path = Path("/workspaces/apex-trader/.env")

load_dotenv(dotenv_path=env_path, override=True)

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient


class AlpacaBroker:
    def __init__(self):
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY")

        self.client = TradingClient(api_key, secret_key, paper=True)

        self.data_client = StockHistoricalDataClient(api_key, secret_key)

    def get_account(self):
        return self.client.get_account()

    def get_positions(self):
        return self.client.get_all_positions()

    def submit_order(self, symbol, qty, side):
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        return self.client.submit_order(order)

    def get_latest_trade(self, symbol):
        from alpaca.data.requests import StockLatestTradeRequest
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        data = self.data_client.get_stock_latest_trade(req)
        return data[symbol]