"""
DecisionEngine — core logic module.

This is NOT a route. It is the brain of the system.
Routes in main.py are thin wrappers around engine.evaluate().

Architecture:
  API → DecisionEngine → [market layer, risk layer, state layer] → Alpaca

Rules are evaluated in order. The first rule that fires wins.
To add a new strategy: add a method to StrategyRules and register it
in DecisionEngine._rules. No routes need to change.
"""

from dataclasses import dataclass, field
from typing import Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta, timezone


# ------------------------------------
# CONFIG (overridable at engine init)
# ------------------------------------

@dataclass
class EngineConfig:
    # Risk gates — mirror the safety config in main.py
    max_position_pct: float = 0.20      # max portfolio % in one symbol
    max_invested_pct: float = 0.90      # max total equity deployed
    max_open_positions: int = 10        # max distinct holdings
    min_cash_buffer: float = 100.0      # minimum cash to keep ($)

    # Strategy thresholds (v1: simple rules)
    stop_loss_pct: float = -0.05        # sell if unrealized P&L < -5%
    take_profit_pct: float = 0.10       # sell if unrealized P&L > +10%
    min_price: float = 1.0              # ignore penny stocks below this price
    lookback_bars: int = 10             # bars used for momentum calculation
    momentum_buy_threshold: float = 0.01  # buy if price is up >1% over lookback
    momentum_sell_threshold: float = -0.01  # sell signal if down >1% over lookback


# ------------------------------------
# RESULT
# ------------------------------------

@dataclass
class Decision:
    symbol: str
    action: str          # "buy" | "sell" | "hold"
    reason: str          # human-readable explanation
    confidence: str      # "high" | "medium" | "low"
    context: dict = field(default_factory=dict)   # supporting data for transparency

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "context": self.context,
        }


# ------------------------------------
# HELPERS
# ------------------------------------

def _normalize_status(raw: str) -> str:
    clean = raw.lower().replace("orderstatus.", "")
    if clean in {"new", "accepted", "pending_new", "held", "pending_cancel", "pending_replace"}:
        return "pending"
    if clean == "filled":
        return "filled"
    if clean == "partially_filled":
        return "partially_filled"
    if clean in {"canceled", "expired", "done_for_day", "replaced", "stopped"}:
        return "canceled"
    if clean == "rejected":
        return "rejected"
    return "unknown"


# ------------------------------------
# DECISION ENGINE
# ------------------------------------

class DecisionEngine:
    def __init__(
        self,
        trading_client: TradingClient,
        data_client: StockHistoricalDataClient,
        config: Optional[EngineConfig] = None,
    ):
        self.trading = trading_client
        self.data = data_client
        self.config = config or EngineConfig()

    # ------ Public API ------

    def evaluate(self, symbol: str) -> Decision:
        """
        Evaluate whether to buy, sell, or hold a symbol.
        Runs all rules in order; first match wins.
        Returns a Decision with full context for transparency.
        """
        sym = symbol.upper()

        # Gather all data first — one pass, no repeated calls
        try:
            snapshot = self._build_snapshot(sym)
        except Exception as e:
            return Decision(
                symbol=sym,
                action="hold",
                reason=f"Could not gather data: {str(e)}",
                confidence="low",
            )

        # Rules evaluated in priority order
        rules = [
            self._rule_risk_gates,
            self._rule_pending_order_exists,
            self._rule_price_too_low,
            self._rule_stop_loss,
            self._rule_take_profit,
            self._rule_position_at_limit,
            self._rule_momentum,
        ]

        for rule in rules:
            decision = rule(sym, snapshot)
            if decision is not None:
                decision.context = snapshot["context"]
                return decision

        # No rule fired → hold by default
        return Decision(
            symbol=sym,
            action="hold",
            reason="No clear signal — conditions do not meet any rule threshold",
            confidence="low",
            context=snapshot["context"],
        )

    # ------ Snapshot builder ------

    def _build_snapshot(self, symbol: str) -> dict:
        """Fetch all layers at once. Returns a single dict the rules share."""
        cfg = self.config

        # Market layer (IEX feed — available on free Alpaca plans)
        trade_req = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
        trade_data = self.data.get_stock_latest_trade(trade_req)
        trade = trade_data[symbol]
        price = float(trade.price)

        # Historical bars for momentum (last N daily bars)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=cfg.lookback_bars * 2)  # buffer for non-trading days
        bars_req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        bars_data = self.data.get_stock_bars(bars_req)
        bars = bars_data[symbol] if symbol in bars_data else []
        bars = list(bars)[-cfg.lookback_bars:]  # keep only last N
        open_price = float(bars[0].open) if bars else None
        momentum_pct = ((price - open_price) / open_price) if open_price else None

        # State layer
        account = self.trading.get_account()
        positions = self.trading.get_all_positions()
        equity = float(account.equity)
        cash = float(account.cash)
        invested = sum(float(p.market_value) for p in positions)

        existing_position = next((p for p in positions if p.symbol == symbol), None)
        position_pct = float(existing_position.market_value) / equity if existing_position and equity > 0 else 0.0
        unrealized_plpc = float(existing_position.unrealized_plpc) if existing_position else None

        # Pending orders for this symbol
        orders_req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        open_orders = self.trading.get_orders(orders_req)
        pending_for_symbol = [
            o for o in open_orders
            if o.symbol == symbol and _normalize_status(str(o.status)) == "pending"
        ]

        context = {
            "price": price,
            "momentum_pct": round(momentum_pct, 4) if momentum_pct is not None else None,
            "lookback_bars": len(bars),
            "equity": equity,
            "cash": cash,
            "invested_pct": round(invested / equity, 4) if equity > 0 else 0,
            "open_positions": len(positions),
            "has_position": existing_position is not None,
            "position_pct": round(position_pct, 4),
            "unrealized_plpc": round(unrealized_plpc, 4) if unrealized_plpc is not None else None,
            "pending_orders": len(pending_for_symbol),
        }

        return {
            "price": price,
            "momentum_pct": momentum_pct,
            "equity": equity,
            "cash": cash,
            "invested_pct": invested / equity if equity > 0 else 0,
            "open_positions": len(positions),
            "existing_position": existing_position,
            "position_pct": position_pct,
            "unrealized_plpc": unrealized_plpc,
            "pending_for_symbol": pending_for_symbol,
            "context": context,
        }

    # ------ Rules ------
    # Each rule returns a Decision if it fires, or None to pass to the next rule.

    def _rule_risk_gates(self, symbol: str, snap: dict) -> Optional[Decision]:
        cfg = self.config
        if snap["cash"] < cfg.min_cash_buffer:
            return Decision(symbol, "hold", f"Risk gate: cash ${snap['cash']:.2f} is below minimum buffer ${cfg.min_cash_buffer}", "high")
        if snap["invested_pct"] > cfg.max_invested_pct:
            return Decision(symbol, "hold", f"Risk gate: {snap['invested_pct']*100:.1f}% of equity deployed (max {cfg.max_invested_pct*100:.0f}%)", "high")
        if snap["open_positions"] >= cfg.max_open_positions and not snap["existing_position"]:
            return Decision(symbol, "hold", f"Risk gate: already at max {cfg.max_open_positions} open positions", "high")
        return None

    def _rule_pending_order_exists(self, symbol: str, snap: dict) -> Optional[Decision]:
        if snap["pending_for_symbol"]:
            return Decision(symbol, "hold", f"Pending order already exists for {symbol} — wait for it to resolve", "high")
        return None

    def _rule_price_too_low(self, symbol: str, snap: dict) -> Optional[Decision]:
        if snap["price"] < self.config.min_price:
            return Decision(symbol, "hold", f"Price ${snap['price']:.4f} is below minimum ${self.config.min_price} (penny stock filter)", "high")
        return None

    def _rule_stop_loss(self, symbol: str, snap: dict) -> Optional[Decision]:
        plpc = snap["unrealized_plpc"]
        if plpc is not None and plpc < self.config.stop_loss_pct:
            return Decision(symbol, "sell", f"Stop-loss triggered: unrealized P&L is {plpc*100:.2f}% (threshold {self.config.stop_loss_pct*100:.0f}%)", "high")
        return None

    def _rule_take_profit(self, symbol: str, snap: dict) -> Optional[Decision]:
        plpc = snap["unrealized_plpc"]
        if plpc is not None and plpc > self.config.take_profit_pct:
            return Decision(symbol, "sell", f"Take-profit triggered: unrealized P&L is {plpc*100:.2f}% (threshold +{self.config.take_profit_pct*100:.0f}%)", "high")
        return None

    def _rule_position_at_limit(self, symbol: str, snap: dict) -> Optional[Decision]:
        if snap["position_pct"] >= self.config.max_position_pct:
            return Decision(symbol, "hold", f"Position at limit: {snap['position_pct']*100:.1f}% of portfolio (max {self.config.max_position_pct*100:.0f}%)", "medium")
        return None

    def _rule_momentum(self, symbol: str, snap: dict) -> Optional[Decision]:
        m = snap["momentum_pct"]
        if m is None:
            return Decision(snap.get("symbol", symbol), "hold", "Insufficient price history for momentum calculation", "low")
        cfg = self.config
        if m >= cfg.momentum_buy_threshold and not snap["existing_position"]:
            return Decision(symbol, "buy", f"Momentum buy: price up {m*100:.2f}% over {cfg.lookback_bars} bars (threshold +{cfg.momentum_buy_threshold*100:.1f}%)", "medium")
        if m <= cfg.momentum_sell_threshold and snap["existing_position"]:
            return Decision(symbol, "sell", f"Momentum sell: price down {m*100:.2f}% over {cfg.lookback_bars} bars (threshold {cfg.momentum_sell_threshold*100:.1f}%)", "medium")
        return None
