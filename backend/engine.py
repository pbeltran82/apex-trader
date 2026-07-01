"""
DecisionEngine — core logic module.

Architecture (layered, inside-out):

  API
   └── DecisionEngine.evaluate(symbol)
         ├── SnapshotBuilder.build()     → MarketSnapshot   (pure data, no logic)
         ├── RiskEvaluator.check()       → list[RiskViolation]  (hard blocks)
         └── StrategyEvaluator.generate() → Signal          (soft signals)

Rules for adding new behavior:
  - New data field?        → add to MarketSnapshot + SnapshotBuilder
  - New hard constraint?   → add a method to RiskEvaluator
  - New trading strategy?  → add a method to StrategyEvaluator
  - Route (main.py)?       → never changes
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta, timezone


# ------------------------------------
# CONFIG
# ------------------------------------

@dataclass
class EngineConfig:
    # Risk gates
    max_position_pct: float = 0.20       # max portfolio % in one symbol
    max_invested_pct: float = 0.90       # max total equity deployed
    max_open_positions: int = 10         # max distinct holdings
    min_cash_buffer: float = 100.0       # minimum cash to keep ($)

    # Strategy thresholds
    stop_loss_pct: float = -0.05         # sell if unrealized P&L < -5%
    take_profit_pct: float = 0.10        # sell if unrealized P&L > +10%
    min_price: float = 1.0               # penny stock filter
    lookback_bars: int = 10              # bars used for momentum
    momentum_buy_threshold: float = 0.01
    momentum_sell_threshold: float = -0.01


# ------------------------------------
# LAYER 0 — SHARED TYPES
# ------------------------------------

@dataclass
class MarketSnapshot:
    """
    Pure data container. No logic, no Alpaca calls.
    Built once per evaluate() call; shared across all layers.
    """
    symbol: str
    price: float
    momentum_pct: Optional[float]
    lookback_bars: int                    # actual bars returned (may be < requested)
    equity: float
    cash: float
    invested_pct: float
    open_positions: int
    existing_position: Optional[Any]      # Alpaca Position object or None
    position_pct: float                   # this symbol as fraction of portfolio
    unrealized_plpc: Optional[float]
    pending_for_symbol: list              # open orders for this symbol

    def to_context(self) -> dict:
        """Human-readable dict attached to every Decision for transparency."""
        return {
            "price": self.price,
            "momentum_pct": round(self.momentum_pct, 4) if self.momentum_pct is not None else None,
            "lookback_bars": self.lookback_bars,
            "equity": self.equity,
            "cash": self.cash,
            "invested_pct": round(self.invested_pct, 4),
            "open_positions": self.open_positions,
            "has_position": self.existing_position is not None,
            "position_pct": round(self.position_pct, 4),
            "unrealized_plpc": round(self.unrealized_plpc, 4) if self.unrealized_plpc is not None else None,
            "pending_orders": len(self.pending_for_symbol),
        }


@dataclass
class RiskViolation:
    reason: str


@dataclass
class Signal:
    action: str       # "buy" | "sell" | "hold"
    reason: str
    confidence: str   # "high" | "medium" | "low"


@dataclass
class Decision:
    symbol: str
    action: str
    reason: str
    confidence: str
    context: dict = field(default_factory=dict)

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
# LAYER 1 — SNAPSHOT BUILDER (pure data)
# ------------------------------------

class SnapshotBuilder:
    """
    Owns all Alpaca API calls. No trading logic here.
    Returns a fully-populated MarketSnapshot.
    """

    def __init__(
        self,
        trading_client: TradingClient,
        data_client: StockHistoricalDataClient,
        config: EngineConfig,
    ):
        self.trading = trading_client
        self.data = data_client
        self.config = config

    def build(self, symbol: str) -> MarketSnapshot:
        cfg = self.config

        # --- Market data ---
        trade_req = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
        trade_data = self.data.get_stock_latest_trade(trade_req)
        price = float(trade_data[symbol].price)

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
        bars = list(bars_data[symbol]) if symbol in bars_data else []
        bars = bars[-cfg.lookback_bars:]
        open_price = float(bars[0].open) if bars else None
        momentum_pct = ((price - open_price) / open_price) if open_price else None

        # --- Portfolio state ---
        account = self.trading.get_account()
        positions = self.trading.get_all_positions()
        equity = float(account.equity)
        cash = float(account.cash)
        invested = sum(float(p.market_value) for p in positions)

        existing = next((p for p in positions if p.symbol == symbol), None)
        position_pct = float(existing.market_value) / equity if existing and equity > 0 else 0.0
        unrealized_plpc = float(existing.unrealized_plpc) if existing else None

        # --- Open orders ---
        open_orders = self.trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
        pending = [
            o for o in open_orders
            if o.symbol == symbol and _normalize_status(str(o.status)) == "pending"
        ]

        return MarketSnapshot(
            symbol=symbol,
            price=price,
            momentum_pct=momentum_pct,
            lookback_bars=len(bars),
            equity=equity,
            cash=cash,
            invested_pct=invested / equity if equity > 0 else 0.0,
            open_positions=len(positions),
            existing_position=existing,
            position_pct=position_pct,
            unrealized_plpc=unrealized_plpc,
            pending_for_symbol=pending,
        )


# ------------------------------------
# LAYER 2 — RISK EVALUATOR (hard blocks)
# ------------------------------------

class RiskEvaluator:
    """
    Hard constraints only. Each check is independent.
    Returns ALL violations found — not just the first.
    The engine uses the first violation as the hold reason,
    but callers can inspect the full list for diagnostics.
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def check(self, snap: MarketSnapshot) -> list[RiskViolation]:
        checks = [
            self._cash_below_buffer,
            self._portfolio_over_invested,
            self._too_many_positions,
            self._pending_order_exists,
            self._price_too_low,
            self._position_at_limit,
            self._stop_loss,
            self._take_profit,
        ]
        return [v for check in checks for v in ([check(snap)] if check(snap) else [])]

    def _cash_below_buffer(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.cash < self.config.min_cash_buffer:
            return RiskViolation(
                f"Cash ${snap.cash:.2f} is below minimum buffer ${self.config.min_cash_buffer:.2f}"
            )

    def _portfolio_over_invested(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.invested_pct > self.config.max_invested_pct:
            return RiskViolation(
                f"{snap.invested_pct*100:.1f}% of equity deployed "
                f"(max {self.config.max_invested_pct*100:.0f}%)"
            )

    def _too_many_positions(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.open_positions >= self.config.max_open_positions and not snap.existing_position:
            return RiskViolation(
                f"Already at max {self.config.max_open_positions} open positions"
            )

    def _pending_order_exists(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.pending_for_symbol:
            return RiskViolation(
                f"Pending order already exists for {snap.symbol} — wait for it to resolve"
            )

    def _price_too_low(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.price < self.config.min_price:
            return RiskViolation(
                f"Price ${snap.price:.4f} is below minimum ${self.config.min_price} (penny stock filter)"
            )

    def _position_at_limit(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.position_pct >= self.config.max_position_pct:
            return RiskViolation(
                f"Position is {snap.position_pct*100:.1f}% of portfolio "
                f"(max {self.config.max_position_pct*100:.0f}%)"
            )

    def _stop_loss(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.unrealized_plpc is not None and snap.unrealized_plpc < self.config.stop_loss_pct:
            return RiskViolation(
                f"Stop-loss: unrealized P&L is {snap.unrealized_plpc*100:.2f}% "
                f"(threshold {self.config.stop_loss_pct*100:.0f}%)"
            )

    def _take_profit(self, snap: MarketSnapshot) -> Optional[RiskViolation]:
        if snap.unrealized_plpc is not None and snap.unrealized_plpc > self.config.take_profit_pct:
            return RiskViolation(
                f"Take-profit: unrealized P&L is {snap.unrealized_plpc*100:.2f}% "
                f"(threshold +{self.config.take_profit_pct*100:.0f}%)"
            )


# ------------------------------------
# LAYER 3 — STRATEGY EVALUATOR (soft signals)
# ------------------------------------

class StrategyEvaluator:
    """
    Pure strategy logic. Only runs after all risk gates pass.
    Each method is an independent strategy; first match wins.
    To add a new strategy: add a method and register it in _strategies().
    """

    def __init__(self, config: EngineConfig):
        self.config = config

    def generate(self, snap: MarketSnapshot) -> Signal:
        for strategy in self._strategies():
            signal = strategy(snap)
            if signal is not None:
                return signal
        return Signal(
            action="hold",
            reason="No clear signal — conditions do not meet any strategy threshold",
            confidence="low",
        )

    def _strategies(self):
        return [self._momentum]

    def _momentum(self, snap: MarketSnapshot) -> Optional[Signal]:
        m = snap.momentum_pct
        if m is None:
            return Signal(
                action="hold",
                reason=f"Insufficient price history for momentum (got {snap.lookback_bars} bars, need {self.config.lookback_bars})",
                confidence="low",
            )
        cfg = self.config
        if m >= cfg.momentum_buy_threshold and not snap.existing_position:
            return Signal(
                action="buy",
                reason=f"Momentum buy: price up {m*100:.2f}% over {snap.lookback_bars} bars (threshold +{cfg.momentum_buy_threshold*100:.1f}%)",
                confidence="medium",
            )
        if m <= cfg.momentum_sell_threshold and snap.existing_position:
            return Signal(
                action="sell",
                reason=f"Momentum sell: price down {m*100:.2f}% over {snap.lookback_bars} bars (threshold {cfg.momentum_sell_threshold*100:.1f}%)",
                confidence="medium",
            )
        return None


# ------------------------------------
# DECISION ENGINE — orchestrator only
# ------------------------------------

class DecisionEngine:
    """
    Thin orchestrator. Owns no logic of its own.
    Delegates entirely to the three layers above.
    """

    def __init__(
        self,
        trading_client: TradingClient,
        data_client: StockHistoricalDataClient,
        config: Optional[EngineConfig] = None,
    ):
        cfg = config or EngineConfig()
        self.snapshot_builder = SnapshotBuilder(trading_client, data_client, cfg)
        self.risk = RiskEvaluator(cfg)
        self.strategy = StrategyEvaluator(cfg)

    def evaluate(self, symbol: str) -> Decision:
        sym = symbol.upper()

        # Layer 1: gather data
        try:
            snap = self.snapshot_builder.build(sym)
        except Exception as e:
            return Decision(
                symbol=sym,
                action="hold",
                reason=f"Snapshot failed: {str(e)}",
                confidence="low",
            )

        context = snap.to_context()

        # Layer 2: hard blocks — first violation wins
        violations = self.risk.check(snap)
        if violations:
            return Decision(
                symbol=sym,
                action="hold",
                reason=f"Risk block: {violations[0].reason}",
                confidence="high",
                context=context,
            )

        # Layer 3: soft signal
        signal = self.strategy.generate(snap)
        return Decision(
            symbol=sym,
            action=signal.action,
            reason=signal.reason,
            confidence=signal.confidence,
            context=context,
        )
