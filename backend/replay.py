"""
ReplayEngine — counterfactual policy comparison.

Architecture (two-phase):

  Phase 1 — Snapshot stream (policy-independent):
    Fetch bars ONCE. At each bar, compute risk violations and strategy signals
    using a baseline portfolio simulation. These records are fixed — no policy
    can alter them. This is the causal isolation guarantee:

        same market data → same risk output → same strategy signals

  Phase 2 — Policy replay (combiner-swappable):
    Each policy (combiner) simulates its own portfolio over the fixed stream.
    Only the combiner.select() call differs between policies.

    Because each policy runs its own cash/position state, portfolio outcomes
    (final equity, drawdown, trade count) differ — but every policy evaluated
    the SAME violations and signals at every bar.

Design constraints (do not violate):
  - SnapshotRecord must never be mutated in Phase 2.
  - Phase 2 must not call RiskEvaluator or StrategyEvaluator.
  - Adding a new combiner requires only: subclass CombinerBase, add to AVAILABLE_COMBINERS.
"""

from dataclasses import dataclass
from typing import Optional
from collections import Counter, defaultdict

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from engine import (
    EngineConfig,
    MarketSnapshot,
    Signal,
    RiskEvaluator,
    StrategyEvaluator,
    CombinerBase,
    AVAILABLE_COMBINERS,
)
from backtest import BacktestConfig, SimulatedPosition


# ------------------------------------
# PHASE 1 RECORD TYPE
# ------------------------------------

@dataclass
class SnapshotRecord:
    """
    Policy-independent record of one bar's evaluation state.
    Computed once in Phase 1; never re-computed in Phase 2.
    All policies see identical violations and signals.
    """
    date: str
    price: float
    violations: list      # list[RiskViolation] — fixed across all policies
    all_signals: list     # list[Signal] — fixed across all policies


# ------------------------------------
# REPLAY ENGINE
# ------------------------------------

class ReplayEngine:
    """
    Two-phase counterfactual comparison engine.
    Instantiate once per server startup — stateless after init.
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

    # ------------------------------------------------------------------
    # INTERNAL: bar fetch (same pattern as BacktestEngine)
    # ------------------------------------------------------------------

    def _fetch_bars(self, bt_config: BacktestConfig) -> list:
        req = StockBarsRequest(
            symbol_or_symbols=bt_config.symbol.upper(),
            timeframe=TimeFrame.Day,
            start=bt_config.start,
            end=bt_config.end,
            # No feed override — SIP default for historical ranges
        )
        bars_data = self.data.get_stock_bars(req)
        return list(dict(bars_data).get('data', {}).get(bt_config.symbol.upper(), []))

    # ------------------------------------------------------------------
    # PHASE 1: build fixed snapshot stream
    # ------------------------------------------------------------------

    def _build_snapshot_stream(
        self, bars: list, bt_config: BacktestConfig
    ) -> list[SnapshotRecord]:
        """
        Iterates all bars after warmup. At each bar:
          1. Constructs MarketSnapshot from baseline portfolio state.
          2. Runs RiskEvaluator and StrategyEvaluator (once).
          3. Advances baseline portfolio using highest_confidence combiner
             so that subsequent risk evaluations reflect realistic state.

        The baseline portfolio advance (step 3) is purely for making risk
        evaluations realistic — it does NOT determine what any policy trades.
        Each policy gets its own independent portfolio in Phase 2.
        """
        cfg = self.config
        symbol = bt_config.symbol.upper()
        warmup = max(cfg.lookback_bars, cfg.mean_reversion_lookback)
        records: list[SnapshotRecord] = []

        cash = bt_config.initial_cash
        position: Optional[SimulatedPosition] = None
        baseline_combiner = AVAILABLE_COMBINERS["highest_confidence"]()

        for i in range(warmup, len(bars)):
            bar = bars[i]
            price = float(bar.close)
            window = bars[i - cfg.lookback_bars: i + 1]
            close_prices = [float(b.close) for b in window]
            open_price = float(window[0].open) if window else None
            momentum_pct = ((price - open_price) / open_price) if open_price else None

            if position:
                position.current_price = price

            invested = position.market_value if position else 0.0
            equity = cash + invested
            invested_pct = invested / equity if equity > 0 else 0.0
            position_pct = invested / equity if position and equity > 0 else 0.0

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
                existing_position=position,
                position_pct=position_pct,
                unrealized_plpc=position.unrealized_plpc if position else None,
                pending_for_symbol=[],
            )

            violations = self.risk.check(snap)
            all_signals, _ = self.strategy.run_all(snap)

            records.append(SnapshotRecord(
                date=bar.timestamp.date().isoformat(),
                price=price,
                violations=violations,
                all_signals=all_signals,
            ))

            # Advance baseline state so next bar's snapshot reflects it
            if not violations:
                baseline_action = baseline_combiner.select(all_signals).action
                if baseline_action == "buy" and not position:
                    cost = price * bt_config.shares_per_trade
                    if cash >= cost:
                        cash -= cost
                        position = SimulatedPosition(
                            symbol=symbol,
                            qty=bt_config.shares_per_trade,
                            avg_entry_price=price,
                            current_price=price,
                        )
                elif baseline_action == "sell" and position:
                    cash += price * position.qty
                    position = None

        return records

    # ------------------------------------------------------------------
    # PHASE 2: simulate one policy over the fixed stream
    # ------------------------------------------------------------------

    def _run_policy(
        self,
        records: list[SnapshotRecord],
        bt_config: BacktestConfig,
        combiner: CombinerBase,
    ) -> dict:
        """
        Pure portfolio simulation — no data fetching, no risk/strategy re-computation.
        Only combiner.select() changes between policies.
        """
        symbol = bt_config.symbol.upper()
        cash = bt_config.initial_cash
        position: Optional[SimulatedPosition] = None

        equity_curve = []
        risk_blocks = 0
        buy_count = 0
        sell_count = 0
        win_count = 0
        dominance: Counter = Counter()

        for rec in records:
            price = rec.price

            if position:
                position.current_price = price

            if rec.violations:
                risk_blocks += 1
                equity_curve.append({
                    "date": rec.date,
                    "equity": round(cash + (position.market_value if position else 0.0), 2),
                    "price": round(price, 4),
                    "trade": None,
                    "decided_by": "risk_block",
                })
                continue

            selected = combiner.select(rec.all_signals)
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
                    trade_action = "buy"
                    buy_count += 1
                    dominance[selected.name] += 1

            elif selected.action == "sell" and position:
                pnl = (price - position.avg_entry_price) * position.qty
                cash += price * position.qty
                position = None
                trade_action = "sell"
                sell_count += 1
                dominance[selected.name] += 1
                if pnl > 0:
                    win_count += 1

            equity_curve.append({
                "date": rec.date,
                "equity": round(cash + (position.market_value if position else 0.0), 2),
                "price": round(price, 4),
                "trade": trade_action,
                "decided_by": "strategy" if trade_action else "hold",
            })

        final_equity = cash + (position.market_value if position else 0.0)
        total_return = (final_equity - bt_config.initial_cash) / bt_config.initial_cash

        peak = bt_config.initial_cash
        max_dd = 0.0
        for ep in equity_curve:
            if ep["equity"] > peak:
                peak = ep["equity"]
            dd = (peak - ep["equity"]) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return {
            "combiner_rule": combiner.RULE,
            "performance": {
                "total_return_pct": round(total_return, 4),
                "max_drawdown_pct": round(max_dd, 4),
                "win_rate_pct": round(win_count / sell_count * 100, 2) if sell_count > 0 else None,
                "final_equity": round(final_equity, 2),
            },
            "execution": {
                "total_trades": buy_count + sell_count,
                "buy_count": buy_count,
                "sell_count": sell_count,
                "risk_blocks": risk_blocks,
            },
            "attribution_summary": {
                "strategy_dominance": dict(dominance),
            },
            "equity_curve": equity_curve,
        }

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def run(
        self, bt_config: BacktestConfig, policy_names: list[str]
    ) -> dict[str, dict]:
        """
        Full replay: fetch bars once, build snapshot stream once, run each policy.
        Returns {policy_name: result_dict} for all valid requested policies.
        Unknown names are silently dropped.
        """
        bars = self._fetch_bars(bt_config)
        if not bars:
            return {}

        records = self._build_snapshot_stream(bars, bt_config)
        if not records:
            return {}

        policies = {
            name: AVAILABLE_COMBINERS[name]()
            for name in policy_names
            if name in AVAILABLE_COMBINERS
        }

        return {
            name: self._run_policy(records, bt_config, combiner)
            for name, combiner in policies.items()
        }
