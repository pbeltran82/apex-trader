"""
DecisionEngine — core logic module.

Architecture (layered, inside-out):

  API
   └── DecisionEngine.evaluate(symbol)
         ├── SnapshotBuilder.build()      → MarketSnapshot        (pure data, no logic)
         ├── RiskEvaluator.check()        → list[RiskViolation]   (hard blocks)
         ├── StrategyEvaluator.run_all()  → list[Signal]          (all strategies, no voting yet)
         └── Combiner.select()            → Signal                (picks winner from list)

Rules for extending the system:
  - New data field?         → add to MarketSnapshot + SnapshotBuilder
  - New hard constraint?    → add a method to RiskEvaluator
  - New trading strategy?   → subclass Strategy, register in StrategyEvaluator
  - Change how signals mix? → edit Combiner only
  - Route (main.py)?        → never changes
"""

from abc import ABC, abstractmethod
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
    stop_loss_pct: float = -0.05         # sell if unrealized P&L < -5%
    take_profit_pct: float = 0.10        # sell if unrealized P&L > +10%
    min_price: float = 1.0               # penny stock filter

    # Momentum strategy
    lookback_bars: int = 10
    momentum_buy_threshold: float = 0.01
    momentum_sell_threshold: float = -0.01

    # Mean reversion strategy
    mean_reversion_lookback: int = 10    # bars for rolling mean
    mean_reversion_buy_threshold: float = -0.02   # buy if price < mean - 2%
    mean_reversion_sell_threshold: float = 0.02   # sell if price > mean + 2%

    # Breakout strategy
    breakout_lookback: int = 10          # bars for recent high/low range
    breakout_atr_factor: float = 0.005   # min range width to consider valid (0.5% of price)


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
    momentum_pct: Optional[float]        # price change over lookback window
    lookback_bars: int                   # actual bars returned (may differ from requested)
    close_prices: list[float]            # historical close prices (for mean reversion etc.)
    equity: float
    cash: float
    invested_pct: float
    open_positions: int
    existing_position: Optional[Any]     # Alpaca Position object or None
    position_pct: float                  # this symbol as fraction of portfolio
    unrealized_plpc: Optional[float]
    pending_for_symbol: list             # open orders for this symbol

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
    """
    Normalized signal contract. Every strategy must produce this exact shape.
    confidence is always 0.0–1.0 (not a string) so strategies can be compared.
    """
    name: str            # strategy that produced this signal
    action: str          # "buy" | "sell" | "hold"
    confidence: float    # 0.0 (no conviction) → 1.0 (maximum conviction)
    reason: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "action": self.action,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class Decision:
    symbol: str
    action: str
    reason: str
    confidence: str           # "high" | "medium" | "low" — label for API consumers
    confidence_score: float   # 0.0–1.0 — raw float for ranking (scan, backtest, etc.)
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "confidence_score": round(self.confidence_score, 3),
            "context": self.context,
        }


@dataclass
class TradeAttribution:
    """
    Lightweight explainability record for a single decision.
    Answers: "which component made this call, and what did every component see?"

    Designed to travel with TradeEvent in backtest and live attribution mode.
    Lighter than PipelineTrace — no snapshot dump, pure decision provenance.
    """
    decided_by: str    # "risk_block" | "strategy" | "snapshot_error"
    risk: dict         # {blocked, violations: [{reason}]}
    strategy: dict     # {all: [{name, action, confidence}], selected, combiner_rule}

    def to_dict(self) -> dict:
        return {
            "decided_by": self.decided_by,
            "risk": self.risk,
            "strategy": self.strategy,
        }


@dataclass
class PipelineTrace:
    """
    Full pipeline trace returned when debug=true.
    Each stage is independently inspectable.
    """
    symbol: str
    snapshot: dict      # what the world looked like
    risk: dict          # all violations found, blocked flag
    strategies: dict    # all signals from all strategies + selected winner
    decision: dict      # final Decision output

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "snapshot": self.snapshot,
            "risk": self.risk,
            "strategies": self.strategies,
            "decision": self.decision,
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


def _confidence_label(confidence: float) -> str:
    """Convert normalized float confidence to API-facing label."""
    if confidence >= 0.70:
        return "high"
    if confidence >= 0.40:
        return "medium"
    return "low"


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

        # Use the longer of the two lookback windows so both strategies get their bars
        lookback_days = max(cfg.lookback_bars, cfg.mean_reversion_lookback)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days * 2)  # buffer for non-trading days
        bars_req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        bars_data = self.data.get_stock_bars(bars_req)
        bars = list(dict(bars_data).get('data', {}).get(symbol, []))
        bars = bars[-lookback_days:]

        close_prices = [float(b.close) for b in bars]
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
            close_prices=close_prices,
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
# LAYER 3 — STRATEGY INTERFACE + IMPLEMENTATIONS
# ------------------------------------

class Strategy(ABC):
    """
    Shared contract every strategy must satisfy.
    - evaluate() must always return a Signal (never None, never raise)
    - confidence must be in [0.0, 1.0]
    - action must be "buy", "sell", or "hold"
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier used in debug output and combiner logic."""
        ...

    @abstractmethod
    def evaluate(self, snap: MarketSnapshot) -> Signal:
        ...


class MomentumStrategy(Strategy):
    """
    Trend-following: buy when price is up over the lookback window,
    sell when it's down. Conviction scales with magnitude of the move.
    """

    name = "momentum"

    def __init__(self, config: EngineConfig):
        self.config = config

    def evaluate(self, snap: MarketSnapshot) -> Signal:
        m = snap.momentum_pct
        cfg = self.config

        if m is None or snap.lookback_bars < cfg.lookback_bars:
            return Signal(
                name=self.name,
                action="hold",
                confidence=0.10,
                reason=f"Insufficient price history (got {snap.lookback_bars} bars, need {cfg.lookback_bars})",
            )

        if m >= cfg.momentum_buy_threshold and not snap.existing_position:
            # Scale confidence linearly: threshold → 0.55, 3× threshold → 0.85
            raw = min(abs(m) / cfg.momentum_buy_threshold, 3.0)
            confidence = round(0.55 + (raw - 1) / 2 * 0.30, 3)
            return Signal(
                name=self.name,
                action="buy",
                confidence=min(confidence, 0.85),
                reason=f"Price up {m*100:.2f}% over {snap.lookback_bars} bars (threshold +{cfg.momentum_buy_threshold*100:.1f}%)",
                metadata={"momentum_pct": round(m, 4)},
            )

        if m <= cfg.momentum_sell_threshold and snap.existing_position:
            raw = min(abs(m) / abs(cfg.momentum_sell_threshold), 3.0)
            confidence = round(0.55 + (raw - 1) / 2 * 0.30, 3)
            return Signal(
                name=self.name,
                action="sell",
                confidence=min(confidence, 0.85),
                reason=f"Price down {m*100:.2f}% over {snap.lookback_bars} bars (threshold {cfg.momentum_sell_threshold*100:.1f}%)",
                metadata={"momentum_pct": round(m, 4)},
            )

        return Signal(
            name=self.name,
            action="hold",
            confidence=0.30,
            reason=f"Momentum {m*100:.2f}% within neutral band [{cfg.momentum_sell_threshold*100:.1f}%, +{cfg.momentum_buy_threshold*100:.1f}%]",
            metadata={"momentum_pct": round(m, 4)},
        )


class MeanReversionStrategy(Strategy):
    """
    Counter-trend: buy when price is significantly below its rolling mean
    (oversold), sell when significantly above (overbought).
    Complements momentum — they often disagree, making the comparison valuable.
    """

    name = "mean_reversion"

    def __init__(self, config: EngineConfig):
        self.config = config

    def evaluate(self, snap: MarketSnapshot) -> Signal:
        cfg = self.config
        prices = snap.close_prices[-cfg.mean_reversion_lookback:]

        if len(prices) < cfg.mean_reversion_lookback:
            return Signal(
                name=self.name,
                action="hold",
                confidence=0.10,
                reason=f"Insufficient price history (got {len(prices)} bars, need {cfg.mean_reversion_lookback})",
            )

        mean = sum(prices) / len(prices)
        deviation = (snap.price - mean) / mean  # signed: negative = below mean

        if deviation <= cfg.mean_reversion_buy_threshold and not snap.existing_position:
            raw = min(abs(deviation) / abs(cfg.mean_reversion_buy_threshold), 3.0)
            confidence = round(0.50 + (raw - 1) / 2 * 0.25, 3)
            return Signal(
                name=self.name,
                action="buy",
                confidence=min(confidence, 0.75),
                reason=f"Price {deviation*100:.2f}% below {cfg.mean_reversion_lookback}-bar mean ${mean:.2f} (oversold threshold {cfg.mean_reversion_buy_threshold*100:.1f}%)",
                metadata={"deviation_pct": round(deviation, 4), "mean": round(mean, 2)},
            )

        if deviation >= cfg.mean_reversion_sell_threshold and snap.existing_position:
            raw = min(abs(deviation) / abs(cfg.mean_reversion_sell_threshold), 3.0)
            confidence = round(0.50 + (raw - 1) / 2 * 0.25, 3)
            return Signal(
                name=self.name,
                action="sell",
                confidence=min(confidence, 0.75),
                reason=f"Price {deviation*100:.2f}% above {cfg.mean_reversion_lookback}-bar mean ${mean:.2f} (overbought threshold +{cfg.mean_reversion_sell_threshold*100:.1f}%)",
                metadata={"deviation_pct": round(deviation, 4), "mean": round(mean, 2)},
            )

        return Signal(
            name=self.name,
            action="hold",
            confidence=0.25,
            reason=f"Price {deviation*100:.2f}% from mean ${mean:.2f} — within reversion band",
            metadata={"deviation_pct": round(deviation, 4), "mean": round(mean, 2)},
        )


class BreakoutStrategy(Strategy):
    """
    Breakout / breakdown detection.
    Buys when price closes above the recent high (upward breakout).
    Sells when price closes below the recent low (breakdown).

    Intentionally conflicts with MeanReversionStrategy:
      - New high → Breakout: buy,  MeanReversion: sell (overbought)
      - New low  → Breakout: sell, MeanReversion: buy  (oversold)

    This conflict is valuable — it creates multi-way votes that expose real
    differences between combiners (especially consensus vs. highest_confidence).
    """

    name = "breakout"

    def __init__(self, config: EngineConfig):
        self.config = config

    def evaluate(self, snap: MarketSnapshot) -> Signal:
        cfg = self.config
        prices = snap.close_prices

        if len(prices) < cfg.breakout_lookback + 1:
            return Signal(
                name=self.name,
                action="hold",
                confidence=0.10,
                reason=f"Insufficient price history ({len(prices)} bars, need {cfg.breakout_lookback + 1})",
            )

        # Use all bars except the current one to define the range
        lookback = prices[-(cfg.breakout_lookback + 1):-1]
        recent_high = max(lookback)
        recent_low = min(lookback)
        current = snap.price
        range_width = recent_high - recent_low

        # Skip if range is too narrow (consolidation noise)
        min_range = current * cfg.breakout_atr_factor
        if range_width < min_range:
            return Signal(
                name=self.name,
                action="hold",
                confidence=0.15,
                reason=f"Range too narrow (${range_width:.2f} < ${min_range:.2f} threshold)",
                metadata={"recent_high": round(recent_high, 2), "recent_low": round(recent_low, 2)},
            )

        if current > recent_high and not snap.existing_position:
            breakout_pct = (current - recent_high) / recent_high
            raw = min(breakout_pct / cfg.breakout_atr_factor, 3.0)
            confidence = round(min(0.55 + raw * 0.10, 0.90), 3)
            return Signal(
                name=self.name,
                action="buy",
                confidence=confidence,
                reason=f"Price ${current:.2f} broke above {cfg.breakout_lookback}-bar high ${recent_high:.2f} (+{breakout_pct*100:.2f}%)",
                metadata={"recent_high": round(recent_high, 2), "breakout_pct": round(breakout_pct, 4)},
            )

        if current < recent_low and snap.existing_position:
            breakdown_pct = (recent_low - current) / recent_low
            raw = min(breakdown_pct / cfg.breakout_atr_factor, 3.0)
            confidence = round(min(0.55 + raw * 0.10, 0.90), 3)
            return Signal(
                name=self.name,
                action="sell",
                confidence=confidence,
                reason=f"Price ${current:.2f} broke below {cfg.breakout_lookback}-bar low ${recent_low:.2f} (-{breakdown_pct*100:.2f}%)",
                metadata={"recent_low": round(recent_low, 2), "breakdown_pct": round(breakdown_pct, 4)},
            )

        return Signal(
            name=self.name,
            action="hold",
            confidence=0.20,
            reason=f"Price within range [${recent_low:.2f} – ${recent_high:.2f}]",
            metadata={"recent_high": round(recent_high, 2), "recent_low": round(recent_low, 2)},
        )


# ------------------------------------
# LAYER 3 — COMBINER
# ------------------------------------

class CombinerBase(ABC):
    """
    Abstract base for all combiners.
    Each combiner is a pure function: list[Signal] → Signal.
    Subclass, set RULE, implement select().
    """
    RULE: str = ""

    @abstractmethod
    def select(self, signals: list[Signal]) -> Signal: ...


class Combiner(CombinerBase):
    """
    Default combiner: highest-confidence non-hold wins.
    If all strategies hold, picks the highest-confidence hold.
    """

    RULE = "highest_confidence_non_hold_wins"

    def select(self, signals: list[Signal]) -> Signal:
        actionable = [s for s in signals if s.action != "hold"]
        pool = actionable if actionable else signals
        return max(pool, key=lambda s: s.confidence)


class WeightedVotingCombiner(CombinerBase):
    """
    Aggregates signals by summing confidence scores per action.
    The action with the highest total weight wins.
    Useful when multiple strategies should temper each other rather than yield to
    the single most-confident signal.
    """

    RULE = "weighted_voting"

    def select(self, signals: list[Signal]) -> Signal:
        from collections import defaultdict
        weights: dict[str, float] = defaultdict(float)
        for s in signals:
            weights[s.action] += s.confidence

        winning_action = max(weights, key=weights.__getitem__)
        candidates = [s for s in signals if s.action == winning_action]
        return max(candidates, key=lambda s: s.confidence)


class ConsensusCombiner(CombinerBase):
    """
    Only acts when ALL actionable strategies agree on the same direction.
    Any conflict (e.g. one buy + one sell) forces a hold.
    Produces far fewer trades; useful for measuring whether signal agreement
    is a better predictor than raw confidence.
    """

    RULE = "consensus_required"

    def select(self, signals: list[Signal]) -> Signal:
        actionable = [s for s in signals if s.action != "hold"]
        if not actionable:
            return max(signals, key=lambda s: s.confidence)

        actions = {s.action for s in actionable}
        if len(actions) > 1:
            # Conflict — hold
            hold_signals = [s for s in signals if s.action == "hold"]
            conflicting = ", ".join(f"{s.name}:{s.action}" for s in actionable)
            if hold_signals:
                best = max(hold_signals, key=lambda s: s.confidence)
                return Signal(
                    name=best.name,
                    action="hold",
                    confidence=best.confidence,
                    reason=f"No consensus — conflicting signals ({conflicting})",
                )
            return Signal(
                name=actionable[0].name,
                action="hold",
                confidence=0.1,
                reason=f"No consensus — conflicting signals ({conflicting})",
            )

        return max(actionable, key=lambda s: s.confidence)


AVAILABLE_COMBINERS: dict[str, type[CombinerBase]] = {
    "highest_confidence": Combiner,
    "weighted_voting": WeightedVotingCombiner,
    "consensus": ConsensusCombiner,
}


# ------------------------------------
# LAYER 3 — STRATEGY EVALUATOR (orchestrates strategies + combiner)
# ------------------------------------

class StrategyEvaluator:
    """
    Runs all registered strategies against the snapshot.
    Returns the full list (for debug visibility) and the selected winner.
    To add a strategy: instantiate it and add to self._strategies list.
    """

    def __init__(self, config: EngineConfig):
        self._strategies: list[Strategy] = [
            MomentumStrategy(config),
            MeanReversionStrategy(config),
            BreakoutStrategy(config),
        ]
        self._combiner = Combiner()

    def run_all(self, snap: MarketSnapshot) -> tuple[list[Signal], Signal]:
        """
        Returns (all_signals, selected_signal).
        all_signals is the full unfiltered output of every strategy.
        selected_signal is what the combiner chose.
        """
        signals = [s.evaluate(snap) for s in self._strategies]
        selected = self._combiner.select(signals)
        return signals, selected


# ------------------------------------
# DECISION ENGINE — orchestrator only
# ------------------------------------

class DecisionEngine:
    """
    Thin orchestrator. Owns no logic of its own.
    Delegates entirely to the four layers above.
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

        try:
            snap = self.snapshot_builder.build(sym)
        except Exception as e:
            return Decision(
                symbol=sym,
                action="hold",
                reason=f"Snapshot failed: {str(e)}",
                confidence="low",
                confidence_score=0.0,
            )

        context = snap.to_context()

        violations = self.risk.check(snap)
        if violations:
            return Decision(
                symbol=sym,
                action="hold",
                reason=f"Risk block: {violations[0].reason}",
                confidence="high",
                confidence_score=1.0,
                context=context,
            )

        _, selected = self.strategy.run_all(snap)
        return Decision(
            symbol=sym,
            action=selected.action,
            reason=selected.reason,
            confidence=_confidence_label(selected.confidence),
            confidence_score=selected.confidence,
            context=context,
        )

    def evaluate_attributed(self, symbol: str) -> tuple[Decision, TradeAttribution]:
        """
        Same execution path as evaluate().
        Additionally returns a TradeAttribution capturing which component made
        the final call and what every strategy saw — same schema used in backtest.
        """
        sym = symbol.upper()

        try:
            snap = self.snapshot_builder.build(sym)
        except Exception as e:
            error_msg = str(e)
            decision = Decision(sym, "hold", f"Snapshot failed: {error_msg}", "low", 0.0)
            attribution = TradeAttribution(
                decided_by="snapshot_error",
                risk={"blocked": True, "violations": [], "error": error_msg},
                strategy={
                    "skipped": True,
                    "reason": "snapshot failed",
                    "all": [],
                    "selected": None,
                    "combiner_rule": self.strategy._combiner.RULE,
                },
            )
            return decision, attribution

        context = snap.to_context()
        violations = self.risk.check(snap)

        # Always run strategies regardless of risk — attribution shows what they saw
        all_signals, selected = self.strategy.run_all(snap)
        strategy_dict = {
            "all": [s.to_dict() for s in all_signals],
            "selected": selected.to_dict(),
            "combiner_rule": self.strategy._combiner.RULE,
        }

        if violations:
            risk_dict = {
                "blocked": True,
                "violations": [{"reason": v.reason} for v in violations],
            }
            decision = Decision(
                symbol=sym,
                action="hold",
                reason=f"Risk block: {violations[0].reason}",
                confidence="high",
                confidence_score=1.0,
                context=context,
            )
            attribution = TradeAttribution(
                decided_by="risk_block",
                risk=risk_dict,
                strategy=strategy_dict,
            )
        else:
            risk_dict = {"blocked": False, "violations": []}
            decision = Decision(
                symbol=sym,
                action=selected.action,
                reason=selected.reason,
                confidence=_confidence_label(selected.confidence),
                confidence_score=selected.confidence,
                context=context,
            )
            attribution = TradeAttribution(
                decided_by="strategy",
                risk=risk_dict,
                strategy=strategy_dict,
            )

        return decision, attribution

    def evaluate_debug(self, symbol: str) -> PipelineTrace:
        """
        Same execution path as evaluate(). Returns every intermediate result.
        Nothing extra is computed — visibility only, no divergent logic.
        """
        sym = symbol.upper()

        # Stage 1: snapshot
        try:
            snap = self.snapshot_builder.build(sym)
            snapshot_dict = snap.to_context()
        except Exception as e:
            error_msg = str(e)
            return PipelineTrace(
                symbol=sym,
                snapshot={"error": error_msg},
                risk={"blocked": True, "violations": [], "error": "snapshot failed"},
                strategies={"skipped": True, "reason": "snapshot failed", "all": [], "selected": None},
                decision=Decision(sym, "hold", f"Snapshot failed: {error_msg}", "low", 0.0).to_dict(),
            )

        # Stage 2: risk
        violations = self.risk.check(snap)
        risk_blocked = len(violations) > 0
        risk_dict = {
            "blocked": risk_blocked,
            "violations": [{"reason": v.reason} for v in violations],
        }

        # Stage 3: strategies (runs even when risk blocked — for observability)
        all_signals, selected = self.strategy.run_all(snap)
        strategies_dict = {
            "combiner_rule": self.strategy._combiner.RULE,
            "skipped_by_risk": risk_blocked,
            "all": [s.to_dict() for s in all_signals],
            "selected": selected.to_dict(),
        }

        # Stage 4: decision
        if risk_blocked:
            decision = Decision(
                symbol=sym,
                action="hold",
                reason=f"Risk block: {violations[0].reason}",
                confidence="high",
                confidence_score=1.0,
                context=snapshot_dict,
            )
        else:
            decision = Decision(
                symbol=sym,
                action=selected.action,
                reason=selected.reason,
                confidence=_confidence_label(selected.confidence),
                confidence_score=selected.confidence,
                context=snapshot_dict,
            )

        return PipelineTrace(
            symbol=sym,
            snapshot=snapshot_dict,
            risk=risk_dict,
            strategies=strategies_dict,
            decision=decision.to_dict(),
        )
