from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from api import research


def intraday_exit_price(
    *,
    day_open: float,
    day_low: float,
    day_high: float,
    stop_loss: float,
    take_profit: float,
    entered_today: bool,
) -> Tuple[Optional[float], Optional[str]]:
    """Return a conservative daily-bar exit.

    When both stop and target are touched, the stop is assumed to occur first.
    Existing positions are gap-aware. Entry-day positions cannot exit before the
    opening fill, so their stop/target levels are used directly.
    """

    if day_low <= stop_loss:
        return (
            float(stop_loss) if entered_today else min(float(day_open), float(stop_loss)),
            "ENTRY_DAY_STOP_LOSS" if entered_today else "STOP_LOSS",
        )
    if day_high >= take_profit:
        return (
            float(take_profit) if entered_today else max(float(day_open), float(take_profit)),
            "ENTRY_DAY_TAKE_PROFIT" if entered_today else "TAKE_PROFIT",
        )
    return None, None


def _record_exit(
    *,
    symbol: str,
    position: research.Position,
    date: str,
    exit_price: float,
    exit_reason: str,
    slippage: float,
    trades: List[Dict[str, Any]],
) -> Tuple[float, Dict[str, Any]]:
    adjusted_exit = float(exit_price) * (1 - slippage)
    proceeds = position.qty * adjusted_exit
    pnl = proceeds - position.cost
    trade = {
        "symbol": symbol,
        "entry_date": position.entry_date,
        "exit_date": date,
        "qty": position.qty,
        "entry_price": position.entry_price,
        "exit_price": adjusted_exit,
        "pnl": pnl,
        "return_pct": (adjusted_exit / position.entry_price - 1) * 100,
        "exit_reason": exit_reason,
        "entry_score": position.entry_score,
        "holding_bars": position.holding_bars,
    }
    trades.append(trade)
    return proceeds, trade


def simulate_fold_with_entry_day_execution(
    symbol: str,
    bars: List[Dict[str, Any]],
    features: Dict[int, Dict[str, Any]],
    start_index: int,
    end_index: int,
    config: research.StrategyConfig,
) -> Dict[str, Any]:
    cash = research.STARTING_EQUITY
    position: Optional[research.Position] = None
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    slippage = research._slippage_rate()
    cooldown_until = -1

    for execution_index in range(start_index, end_index):
        feature = features.get(execution_index)
        if feature is None:
            continue
        bar = bars[execution_index]
        date = feature["execution_date"]
        day_open = float(bar["open"])
        day_low = float(bar["low"])
        day_high = float(bar["high"])

        if position is not None:
            position.holding_bars += 1
            exit_price, exit_reason = intraday_exit_price(
                day_open=day_open,
                day_low=day_low,
                day_high=day_high,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                entered_today=False,
            )
            if exit_price is None and config.trend_exit and feature["signal_price"] <= feature["sma50"]:
                exit_price = day_open
                exit_reason = "TREND_BREAK"
            elif exit_price is None and position.holding_bars >= config.max_holding_bars:
                exit_price = day_open
                exit_reason = "TIME_EXIT"

            if exit_price is not None and exit_reason is not None:
                proceeds, _ = _record_exit(
                    symbol=symbol,
                    position=position,
                    date=date,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    slippage=slippage,
                    trades=trades,
                )
                cash += proceeds
                position = None
                cooldown_until = execution_index + 1

        if (
            position is None
            and execution_index > cooldown_until
            and research._approved(feature, config)
        ):
            entry_price = day_open * (1 + slippage)
            stop_pct = research._clamp(
                feature["atr_pct"] * config.atr_multiplier,
                0.02,
                0.10,
            )
            target_pct = research._clamp(
                stop_pct * config.reward_risk,
                0.03,
                0.30,
            )
            risk_budget = cash * 0.005
            per_share_risk = entry_price * stop_pct
            qty_by_risk = int(risk_budget // per_share_risk) if per_share_risk > 0 else 0
            qty_by_notional = int((cash * 0.15) // entry_price)
            qty_by_cash = int(cash // entry_price)
            qty = min(qty_by_risk, qty_by_notional, qty_by_cash)

            if qty > 0:
                cost = qty * entry_price
                cash -= cost
                position = research.Position(
                    qty=qty,
                    entry_price=entry_price,
                    cost=cost,
                    stop_loss=entry_price * (1 - stop_pct),
                    take_profit=entry_price * (1 + target_pct),
                    entry_date=date,
                    entry_score=feature["score"],
                )

                # Daily high/low are observed after the opening fill. This closes
                # the optimistic gap in which entry-day stops and targets were
                # previously ignored until the following bar.
                exit_price, exit_reason = intraday_exit_price(
                    day_open=day_open,
                    day_low=day_low,
                    day_high=day_high,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    entered_today=True,
                )
                if exit_price is not None and exit_reason is not None:
                    proceeds, _ = _record_exit(
                        symbol=symbol,
                        position=position,
                        date=date,
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                        slippage=slippage,
                        trades=trades,
                    )
                    cash += proceeds
                    position = None
                    cooldown_until = execution_index + 1

        marked_equity = cash
        if position is not None:
            marked_equity += position.qty * float(bar["close"])
        equity_curve.append({"date": date, "equity": marked_equity})

    if position is not None and end_index > start_index:
        final_bar = bars[end_index - 1]
        final_date = research._date_key(final_bar.get("timestamp"))
        adjusted_exit = float(final_bar["close"]) * (1 - slippage)
        proceeds = position.qty * adjusted_exit
        cash += proceeds
        pnl = proceeds - position.cost
        trades.append(
            {
                "symbol": symbol,
                "entry_date": position.entry_date,
                "exit_date": final_date,
                "qty": position.qty,
                "entry_price": position.entry_price,
                "exit_price": adjusted_exit,
                "pnl": pnl,
                "return_pct": (adjusted_exit / position.entry_price - 1) * 100,
                "exit_reason": "FOLD_END",
                "entry_score": position.entry_score,
                "holding_bars": position.holding_bars,
            }
        )
        equity_curve.append({"date": final_date, "equity": cash})

    benchmark_return = (
        (float(bars[end_index - 1]["close"]) / float(bars[start_index]["open"]) - 1)
        * 100
        if end_index > start_index
        else 0.0
    )
    return {
        "symbol": symbol,
        "period": {
            "start": research._date_key(bars[start_index].get("timestamp")),
            "end": research._date_key(bars[end_index - 1].get("timestamp")),
            "bars": end_index - start_index,
        },
        "performance": research._performance(
            cash,
            trades,
            equity_curve,
            benchmark_return,
        ),
    }


def install_research_execution_model() -> None:
    if getattr(research, "_entry_day_execution_installed", False):
        return

    original_research = research.run_strategy_research

    def research_with_execution_metadata(symbols: List[str]) -> Dict[str, Any]:
        result = original_research(symbols)
        if result.get("ok"):
            result.setdefault("method", {})["entry_day_stop_target"] = (
                "EVALUATED_WITH_STOP_FIRST_CONSERVATIVE_ORDERING"
            )
        return result

    research._simulate_fold = simulate_fold_with_entry_day_execution
    research.run_strategy_research = research_with_execution_metadata
    research.ENTRY_DAY_EXECUTION_MODEL = "STOP_FIRST"
    research._entry_day_execution_installed = True
