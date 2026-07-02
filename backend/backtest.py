"""
BacktestEngine — replays the decision pipeline over historical data.

Design contract (critical):
  - SnapshotBuilder is NOT used here.
  - MarketSnapshot objects are constructed directly from historical bars.
  - RiskEvaluator and StrategyEvaluator are reused UNCHANGED.
  - The engine under test is identical to the live engine — input source differs, not logic.

This means:
  - A strategy that passes backtest uses the exact same code as one running live.
  - Any change to strategy logic automatically affects both live and backtest.
  - There is no "backtest version" of the engine — only one engine.

Limitations (v1, intentional):
  - Fixed position size (shares_per_trade)
  - Fills at bar close (no slippage modeling)
  - Single position per symbol at a time
  - No transaction costs
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from engine import (
    EngineConfig,
    MarketSnapshot,
    TradeAttribution,
    RiskEvaluator,
    StrategyEvaluator,
    Combiner,
)


# ------------------------------------
# SIMULATED PORTFOLIO TYPES
# ------------------------------------

@dataclass
class SimulatedPosition:
    """
    Minimal stand-in for an Alpaca Position object.
    Only needs to be truthy — the actual values are passed via snapshot fields.
    Risk and strategy layers never call methods on existing_position directly.
    """
    symbol: str
    qty: int
    avg_entry_price: float
    current_price: float

    @property
    def market_value(self) -> float:
        return self.qty * self.current_price

    @property
    def unrealized_plpc(self) -> float:
        return (self.current_price - self.avg_entry_price) / self.avg_entry_price


@dataclass
class EquityPoint:
    """
    One data point on the equity curve — recorded at every bar after warmup.
    Equity is post-trade (reflects any fill that happened on this bar).
    `trade` is "buy" | "sell" | None — lets consumers overlay trade markers.
    `decided_by` is "risk_block" | "strategy" | "hold" — attribution summary for this bar.
    """
    date: str
    equity: float
    price: float
    trade: Optional[str] = None       # "buy" | "sell" | None
    decided_by: Optional[str] = None  # "risk_block" | "strategy" | "hold"


@dataclass
class TradeEvent:
    date: str
    action: str           # "buy" | "sell"
    price: float          # fill price (bar close)
    qty: int
    reason: str           # which strategy + signal fired
    cash_before: float
    cash_after: float
    realized_pnl: Optional[float]          # None for buys; P&L for sells
    attribution: Optional[dict] = None     # TradeAttribution.to_dict() — who made the call


@dataclass
class BacktestResult:
    symbol: str
    start: str
    end: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    bars_evaluated: int
    warmup_bars: int            # bars consumed before first evaluation
    total_trades: int
    buy_count: int
    sell_count: int
    win_count: int              # sells with positive realized P&L
    loss_count: int
    risk_blocks: int            # bars where risk gating blocked strategy
    max_drawdown_pct: float = 0.0
    strategy_dominance: dict = field(default_factory=dict)  # {strategy_name: count}
    trades: list[TradeEvent] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "period": {"start": self.start, "end": self.end},
            "capital": {
                "initial_cash": self.initial_cash,
                "final_equity": round(self.final_equity, 2),
                "total_return_pct": round(self.total_return_pct, 4),
            },
            "execution": {
                "bars_evaluated": self.bars_evaluated,
                "warmup_bars": self.warmup_bars,
                "risk_blocks": self.risk_blocks,
                "total_trades": self.total_trades,
                "buy_count": self.buy_count,
                "sell_count": self.sell_count,
            },
            "performance": {
                "win_count": self.win_count,
                "loss_count": self.loss_count,
                "win_rate_pct": round(
                    self.win_count / self.sell_count * 100, 2
                ) if self.sell_count > 0 else None,
                "max_drawdown_pct": self.max_drawdown_pct,
            },
            "attribution_summary": {
                "strategy_dominance": self.strategy_dominance,
            },
            "equity_curve": [
                {
                    "date": ep.date,
                    "equity": ep.equity,
                    "price": ep.price,
                    "trade": ep.trade,
                    "decided_by": ep.decided_by,
                }
                for ep in self.equity_curve
            ],
            "trades": [
                {
                    "date": t.date,
                    "action": t.action,
                    "price": round(t.price, 4),
                    "qty": t.qty,
                    "reason": t.reason,
                    "realized_pnl": round(t.realized_pnl, 4) if t.realized_pnl is not None else None,
                    "attribution": t.attribution,
                }
                for t in self.trades
            ],
        }


# ------------------------------------
# BACKTEST CONFIG
# ------------------------------------

@dataclass
class BacktestConfig:
    symbol: str
    start: datetime
    end: datetime
    initial_cash: float = 100_000.0
    shares_per_trade: int = 1


# ------------------------------------
# BACKTEST ENGINE
# ------------------------------------

class BacktestEngine:
    """
    Replays RiskEvaluator + StrategyEvaluator over historical bars.
    Does NOT use SnapshotBuilder — constructs MarketSnapshot directly.
    """

    def __init__(
        self,
        data_client: StockHistoricalDataClient,
        engine_config: Optional[EngineConfig] = None,
    ):
        self.data = data_client
        self.config = engine_config or EngineConfig()
        self.risk = RiskEvaluator(self.config)
        self.strategy = StrategyEvaluator(self.config)
        self.combiner = Combiner()

    def run(self, bt_config: BacktestConfig) -> BacktestResult:
        cfg = self.config
        symbol = bt_config.symbol.upper()

        # Fetch full bar history once — one round trip
        bars_req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=bt_config.start,
            end=bt_config.end,
            # No feed override — default SIP is available for historical ranges
            # IEX does not serve historical daily bars
        )
        bars_data = self.data.get_stock_bars(bars_req)
        bars = list(dict(bars_data).get('data', {}).get(symbol, []))

        # Warmup = enough bars for the longest lookback window
        warmup = max(cfg.lookback_bars, cfg.mean_reversion_lookback)

        if len(bars) <= warmup:
            return BacktestResult(
                symbol=symbol,
                start=bt_config.start.date().isoformat(),
                end=bt_config.end.date().isoformat(),
                initial_cash=bt_config.initial_cash,
                final_equity=bt_config.initial_cash,
                total_return_pct=0.0,
                bars_evaluated=0,
                warmup_bars=len(bars),
                total_trades=0,
                buy_count=0,
                sell_count=0,
                win_count=0,
                loss_count=0,
                risk_blocks=0,
            )

        # --- Simulated portfolio state ---
        cash = bt_config.initial_cash
        position: Optional[SimulatedPosition] = None

        # --- Result accumulators ---
        trades: list[TradeEvent] = []
        equity_curve: list[EquityPoint] = []
        risk_blocks = 0

        # --- Main loop: one bar at a time after warmup ---
        for i in range(warmup, len(bars)):
            bar = bars[i]
            price = float(bar.close)

            # Build the lookback window (same logic as SnapshotBuilder)
            window = bars[i - cfg.lookback_bars: i + 1]
            close_prices = [float(b.close) for b in window]
            open_price = float(window[0].open) if window else None
            momentum_pct = ((price - open_price) / open_price) if open_price else None

            # Simulated portfolio metrics
            if position:
                position.current_price = price
            invested = position.market_value if position else 0.0
            equity = cash + invested
            invested_pct = invested / equity if equity > 0 else 0.0
            position_pct = invested / equity if position and equity > 0 else 0.0
            unrealized_plpc = position.unrealized_plpc if position else None

            snap = MarketSnapshot(
                symbol=symbol,
                price=price,
                momentum_pct=momentum_pct,
                lookback_bars=len(window),
                close_prices=close_prices,
                equity=equity,
                cash=cash,
                invested_pct=invested_pct,
                open_positions=1 if position else 0,
                existing_position=position,   # None or SimulatedPosition (truthy only)
                position_pct=position_pct,
                unrealized_plpc=unrealized_plpc,
                pending_for_symbol=[],        # no pending orders in simulation
            )

            # Risk layer (unchanged from live engine)
            violations = self.risk.check(snap)

            # Strategy layer always runs — needed for attribution even on risk block
            all_signals, selected = self.strategy.run_all(snap)

            # Build attribution for this bar (attached to trade events below)
            attribution = TradeAttribution(
                decided_by="risk_block" if violations else "strategy",
                risk={
                    "blocked": bool(violations),
                    "violations": [{"reason": v.reason} for v in violations],
                },
                strategy={
                    "all": [s.to_dict() for s in all_signals],
                    "selected": selected.to_dict(),
                    "combiner_rule": self.combiner.RULE,
                },
            )

            date_str = bar.timestamp.date().isoformat()

            if violations:
                risk_blocks += 1
                # Record equity point even on risk blocks (equity unchanged this bar)
                equity_curve.append(EquityPoint(
                    date=date_str,
                    equity=round(cash + (position.market_value if position else 0.0), 2),
                    price=round(price, 4),
                    trade=None,
                    decided_by="risk_block",
                ))
                continue

            # Simulate fill at bar close
            trade_action: Optional[str] = None

            if selected.action == "buy" and not position:
                cost = price * bt_config.shares_per_trade
                if cash >= cost:
                    cash -= cost
                    position = SimulatedPosition(
                        symbol=symbol,
                        qty=bt_config.shares_per_trade,
                        avg_entry_price=price,
                        current_price=price,
                    )
                    trades.append(TradeEvent(
                        date=date_str,
                        action="buy",
                        price=price,
                        qty=bt_config.shares_per_trade,
                        reason=selected.reason,
                        cash_before=cash + cost,
                        cash_after=cash,
                        realized_pnl=None,
                        attribution=attribution.to_dict(),
                    ))
                    trade_action = "buy"

            elif selected.action == "sell" and position:
                proceeds = price * position.qty
                pnl = (price - position.avg_entry_price) * position.qty
                cash += proceeds
                trades.append(TradeEvent(
                    date=date_str,
                    action="sell",
                    price=price,
                    qty=position.qty,
                    reason=selected.reason,
                    cash_before=cash - proceeds,
                    cash_after=cash,
                    realized_pnl=pnl,
                    attribution=attribution.to_dict(),
                ))
                position = None
                trade_action = "sell"

            # Record post-trade equity point for this bar
            equity_curve.append(EquityPoint(
                date=date_str,
                equity=round(cash + (position.market_value if position else 0.0), 2),
                price=round(price, 4),
                trade=trade_action,
                decided_by="strategy" if trade_action else "hold",
            ))

        # Mark-to-market at end: close any open position at last bar price
        if position and bars:
            final_price = float(bars[-1].close)
            position.current_price = final_price

        final_equity = cash + (position.market_value if position else 0.0)
        total_return_pct = (final_equity - bt_config.initial_cash) / bt_config.initial_cash

        sell_trades = [t for t in trades if t.action == "sell"]
        win_count = sum(1 for t in sell_trades if (t.realized_pnl or 0) > 0)

        # --- Derived stats from equity curve ---
        peak = bt_config.initial_cash
        max_drawdown = 0.0
        for ep in equity_curve:
            if ep.equity > peak:
                peak = ep.equity
            dd = (peak - ep.equity) / peak if peak > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

        # Strategy dominance: count how often each strategy name won the combiner
        from collections import Counter
        dominance: Counter = Counter()
        for t in trades:
            if t.attribution:
                sel = t.attribution.get("strategy", {}).get("selected")
                if sel and sel.get("name"):
                    dominance[sel["name"]] += 1

        return BacktestResult(
            symbol=symbol,
            start=bt_config.start.date().isoformat(),
            end=bt_config.end.date().isoformat(),
            initial_cash=bt_config.initial_cash,
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            bars_evaluated=len(bars) - warmup,
            warmup_bars=warmup,
            total_trades=len(trades),
            buy_count=sum(1 for t in trades if t.action == "buy"),
            sell_count=len(sell_trades),
            win_count=win_count,
            loss_count=len(sell_trades) - win_count,
            risk_blocks=risk_blocks,
            max_drawdown_pct=round(max_drawdown, 4),
            strategy_dominance=dict(dominance),
            trades=trades,
            equity_curve=equity_curve,
        )
