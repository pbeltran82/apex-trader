from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from statistics import mean, median
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from api.backtest import MIN_HISTORY, STARTING_EQUITY, _date_key, _max_drawdown, _slippage_rate
from api.historical_data import get_daily_bars
from api.intelligence import _clamp, _completed_bars


RESEARCH_LOOKBACK_DAYS = 10 * 365
RESEARCH_BAR_LIMIT = 3_000
RESEARCH_FOLDS = 4
RESEARCH_CACHE_SECONDS = 6 * 60 * 60
TOP_RESULT_COUNT = 10

_cache_lock = threading.Lock()
_research_cache: Dict[str, Any] = {}


@dataclass(frozen=True)
class StrategyConfig:
    threshold: int
    atr_multiplier: float
    reward_risk: float
    max_holding_bars: int
    relative_strength_filter: bool
    trend_exit: bool


@dataclass
class Position:
    qty: int
    entry_price: float
    cost: float
    stop_loss: float
    take_profit: float
    entry_date: str
    entry_score: int
    holding_bars: int = 0


def _prefix(values: Iterable[float]) -> List[float]:
    output = [0.0]
    running = 0.0
    for value in values:
        running += float(value)
        output.append(running)
    return output


def _window_mean(prefix: List[float], start: int, end: int) -> Optional[float]:
    if start < 0 or end <= start or end >= len(prefix):
        return None
    return (prefix[end] - prefix[start]) / (end - start)


def _pct_change(current: float, reference: float) -> float:
    return (current - reference) / reference if reference else 0.0


def _true_ranges(bars: List[Dict[str, Any]]) -> List[float]:
    values: List[float] = []
    for index, bar in enumerate(bars):
        high = float(bar["high"])
        low = float(bar["low"])
        if index == 0:
            values.append(max(0.0, high - low))
            continue
        previous_close = float(bars[index - 1]["close"])
        values.append(
            max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
    return values


def _index_series(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    dates = [_date_key(bar.get("timestamp")) for bar in bars]
    closes = [float(bar["close"]) for bar in bars]
    close_prefix = _prefix(closes)
    states: List[Optional[Dict[str, float]]] = [None] * len(bars)

    for index in range(len(bars)):
        if index < 199:
            continue
        sma50 = _window_mean(close_prefix, index - 49, index + 1)
        sma200 = _window_mean(close_prefix, index - 199, index + 1)
        if sma50 is None or sma200 is None:
            continue
        return20 = _pct_change(closes[index], closes[index - 20]) if index >= 20 else 0.0
        return60 = _pct_change(closes[index], closes[index - 60]) if index >= 60 else 0.0
        states[index] = {
            "price": closes[index],
            "sma50": sma50,
            "sma200": sma200,
            "return20": return20,
            "return60": return60,
        }

    return {"dates": dates, "states": states}


def _lookup_index_state(series: Dict[str, Any], signal_date: str) -> Optional[Dict[str, float]]:
    position = bisect_right(series["dates"], signal_date) - 1
    if position < 0:
        return None
    return series["states"][position]


def _regime_for_date(index_series: Dict[str, Dict[str, Any]], signal_date: str) -> Dict[str, Any]:
    diagnostics = []
    score = 0.0
    spy_return60: Optional[float] = None

    for symbol in ("SPY", "QQQ"):
        state = _lookup_index_state(index_series[symbol], signal_date)
        if state is None:
            diagnostics.append({"symbol": symbol, "ok": False})
            continue

        component = 0.0
        component += 2.5 if state["price"] > state["sma50"] else 0.0
        component += 2.5 if state["sma50"] > state["sma200"] else 0.0
        component += 2.5 if state["return20"] > 0 else 0.0
        score += component
        if symbol == "SPY":
            spy_return60 = state["return60"]
        diagnostics.append(
            {
                "symbol": symbol,
                "ok": True,
                "score": component,
                "return20_pct": round(state["return20"] * 100, 2),
                "return60_pct": round(state["return60"] * 100, 2),
            }
        )

    if len([row for row in diagnostics if row.get("ok")]) < 2:
        return {
            "regime": "UNKNOWN",
            "score": 0.0,
            "trade_allowed": False,
            "spy_return60": spy_return60,
            "indexes": diagnostics,
        }
    if score >= 12.5:
        regime = "BULLISH"
        allowed = True
    elif score >= 7.5:
        regime = "MIXED"
        allowed = True
    else:
        regime = "RISK_OFF"
        allowed = False
    return {
        "regime": regime,
        "score": score,
        "trade_allowed": allowed,
        "spy_return60": spy_return60,
        "indexes": diagnostics,
    }


def _feature_rows(
    bars: List[Dict[str, Any]],
    index_series: Dict[str, Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    closes = [float(bar["close"]) for bar in bars]
    volumes = [float(bar.get("volume") or 0) for bar in bars]
    close_prefix = _prefix(closes)
    volume_prefix = _prefix(volumes)
    range_prefix = _prefix(_true_ranges(bars))
    rows: Dict[int, Dict[str, Any]] = {}

    # execution_index is the bar where a prior-close signal executes at the open.
    for execution_index in range(MIN_HISTORY, len(bars)):
        signal_index = execution_index - 1
        signal_price = closes[signal_index]
        sma20 = _window_mean(close_prefix, execution_index - 20, execution_index)
        sma50 = _window_mean(close_prefix, execution_index - 50, execution_index)
        sma200 = _window_mean(close_prefix, execution_index - 200, execution_index)
        average_volume20 = _window_mean(
            volume_prefix,
            execution_index - 21,
            execution_index - 1,
        )
        atr14 = _window_mean(range_prefix, execution_index - 14, execution_index)
        if None in (sma20, sma50, sma200, average_volume20, atr14):
            continue

        return20 = _pct_change(signal_price, closes[execution_index - 21])
        return60 = _pct_change(signal_price, closes[execution_index - 61])
        volume_ratio = (
            volumes[signal_index] / average_volume20 if average_volume20 else 1.0
        )
        atr_pct = atr14 / signal_price if signal_price else 0.0
        signal_date = _date_key(bars[signal_index].get("timestamp"))
        regime = _regime_for_date(index_series, signal_date)

        trend_score = 0.0
        trend_score += 8 if signal_price > sma20 else 0.0
        trend_score += 8 if sma20 > sma50 else 0.0
        trend_score += 8 if sma50 > sma200 else 0.0
        trend_score += 6 if signal_price > sma200 else 0.0
        momentum_score = _clamp(
            12.5 + (return20 * 100 * 0.8) + (return60 * 100 * 0.25),
            0,
            25,
        )
        volume_score = _clamp(7.5 + ((volume_ratio - 1.0) * 7.5), 0, 15)
        atr_points = atr_pct * 100
        if 1.0 <= atr_points <= 4.0:
            volatility_score = 15.0
        elif 0.5 <= atr_points <= 5.5:
            volatility_score = 11.0
        elif atr_points <= 7.0:
            volatility_score = 7.0
        else:
            volatility_score = 3.0

        score = int(
            round(
                _clamp(
                    trend_score
                    + momentum_score
                    + volume_score
                    + volatility_score
                    + float(regime["score"]),
                    0,
                    100,
                )
            )
        )
        spy_return60 = regime.get("spy_return60")
        relative_strength60 = (
            return60 - float(spy_return60)
            if spy_return60 is not None
            else None
        )

        rows[execution_index] = {
            "signal_date": signal_date,
            "execution_date": _date_key(bars[execution_index].get("timestamp")),
            "signal_price": signal_price,
            "sma50": float(sma50),
            "sma200": float(sma200),
            "return20": return20,
            "return60": return60,
            "relative_strength60": relative_strength60,
            "volume_ratio20": volume_ratio,
            "atr_pct": atr_pct,
            "score": score,
            "regime": regime,
        }

    return rows


def _approved(feature: Dict[str, Any], config: StrategyConfig) -> bool:
    regime = feature["regime"]
    threshold = config.threshold + (5 if regime["regime"] == "MIXED" else 0)
    filters = [
        bool(regime["trade_allowed"]),
        feature["signal_price"] > feature["sma50"],
        feature["sma50"] > feature["sma200"],
        feature["return20"] > 0,
        feature["score"] >= threshold,
    ]
    if config.relative_strength_filter:
        filters.append(
            feature["relative_strength60"] is not None
            and feature["relative_strength60"] > 0
        )
    return all(filters)


def _performance(
    cash: float,
    trades: List[Dict[str, Any]],
    equity_curve: List[Dict[str, Any]],
    benchmark_return_pct: float,
) -> Dict[str, Any]:
    wins = [trade for trade in trades if trade["pnl"] > 0]
    losses = [trade for trade in trades if trade["pnl"] < 0]
    gross_profit = sum(trade["pnl"] for trade in wins)
    gross_loss = abs(sum(trade["pnl"] for trade in losses))
    total_return_pct = (cash / STARTING_EQUITY - 1) * 100
    return {
        "ending_equity": round(cash, 2),
        "total_return_pct": round(total_return_pct, 4),
        "benchmark_return_pct": round(benchmark_return_pct, 4),
        "excess_return_pct": round(total_return_pct - benchmark_return_pct, 4),
        "max_drawdown_pct": round(_max_drawdown(equity_curve) * 100, 4),
        "trade_count": len(trades),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 4) if trades else 0.0,
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "average_trade_return_pct": round(
            mean(trade["return_pct"] for trade in trades), 4
        ) if trades else 0.0,
    }


def _simulate_fold(
    symbol: str,
    bars: List[Dict[str, Any]],
    features: Dict[int, Dict[str, Any]],
    start_index: int,
    end_index: int,
    config: StrategyConfig,
) -> Dict[str, Any]:
    cash = STARTING_EQUITY
    position: Optional[Position] = None
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    slippage = _slippage_rate()
    cooldown_until = -1

    for execution_index in range(start_index, end_index):
        feature = features.get(execution_index)
        if feature is None:
            continue
        bar = bars[execution_index]
        date = feature["execution_date"]

        if position is not None:
            position.holding_bars += 1
            day_open = float(bar["open"])
            day_low = float(bar["low"])
            day_high = float(bar["high"])
            exit_price: Optional[float] = None
            exit_reason: Optional[str] = None

            if day_low <= position.stop_loss:
                exit_price = min(day_open, position.stop_loss)
                exit_reason = "STOP_LOSS"
            elif day_high >= position.take_profit:
                exit_price = max(day_open, position.take_profit)
                exit_reason = "TAKE_PROFIT"
            elif config.trend_exit and feature["signal_price"] <= feature["sma50"]:
                exit_price = day_open
                exit_reason = "TREND_BREAK"
            elif position.holding_bars >= config.max_holding_bars:
                exit_price = day_open
                exit_reason = "TIME_EXIT"

            if exit_price is not None:
                adjusted_exit = float(exit_price) * (1 - slippage)
                proceeds = position.qty * adjusted_exit
                cash += proceeds
                pnl = proceeds - position.cost
                trades.append(
                    {
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
                )
                position = None
                cooldown_until = execution_index + 1

        if (
            position is None
            and execution_index > cooldown_until
            and _approved(feature, config)
        ):
            entry_price = float(bar["open"]) * (1 + slippage)
            stop_pct = _clamp(feature["atr_pct"] * config.atr_multiplier, 0.02, 0.10)
            target_pct = _clamp(stop_pct * config.reward_risk, 0.03, 0.30)
            risk_budget = cash * 0.005
            per_share_risk = entry_price * stop_pct
            qty_by_risk = int(risk_budget // per_share_risk) if per_share_risk > 0 else 0
            qty_by_notional = int((cash * 0.15) // entry_price)
            qty_by_cash = int(cash // entry_price)
            qty = min(qty_by_risk, qty_by_notional, qty_by_cash)
            if qty > 0:
                cost = qty * entry_price
                cash -= cost
                position = Position(
                    qty=qty,
                    entry_price=entry_price,
                    cost=cost,
                    stop_loss=entry_price * (1 - stop_pct),
                    take_profit=entry_price * (1 + target_pct),
                    entry_date=date,
                    entry_score=feature["score"],
                )

        marked_equity = cash
        if position is not None:
            marked_equity += position.qty * float(bar["close"])
        equity_curve.append({"date": date, "equity": marked_equity})

    if position is not None and end_index > start_index:
        final_bar = bars[end_index - 1]
        final_date = _date_key(final_bar.get("timestamp"))
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
            "start": _date_key(bars[start_index].get("timestamp")),
            "end": _date_key(bars[end_index - 1].get("timestamp")),
            "bars": end_index - start_index,
        },
        "performance": _performance(cash, trades, equity_curve, benchmark_return),
    }


def _fold_ranges(bar_count: int) -> List[Tuple[int, int]]:
    eligible = bar_count - MIN_HISTORY
    if eligible < RESEARCH_FOLDS * 60:
        return []
    boundaries = [
        MIN_HISTORY + math.floor(eligible * fold / RESEARCH_FOLDS)
        for fold in range(RESEARCH_FOLDS + 1)
    ]
    boundaries[-1] = bar_count
    return [
        (boundaries[index], boundaries[index + 1])
        for index in range(RESEARCH_FOLDS)
    ]


def _aggregate(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    performances = [cell["performance"] for cell in cells]
    returns = [float(row["total_return_pct"]) for row in performances]
    drawdowns = [float(row["max_drawdown_pct"]) for row in performances]
    gross_profit = sum(float(row["gross_profit"]) for row in performances)
    gross_loss = sum(float(row["gross_loss"]) for row in performances)
    total_trades = sum(int(row["trade_count"]) for row in performances)
    by_symbol: Dict[str, List[float]] = {}
    for cell in cells:
        by_symbol.setdefault(cell["symbol"], []).append(
            float(cell["performance"]["total_return_pct"])
        )
    symbol_returns = {
        symbol: round(mean(values), 4) for symbol, values in by_symbol.items()
    }
    positive_symbols = sum(value > 0 for value in symbol_returns.values())

    return {
        "cell_count": len(cells),
        "median_return_pct": round(median(returns), 4) if returns else 0.0,
        "average_return_pct": round(mean(returns), 4) if returns else 0.0,
        "positive_cell_rate_pct": round(
            sum(value > 0 for value in returns) / len(returns) * 100, 2
        ) if returns else 0.0,
        "positive_symbol_rate_pct": round(
            positive_symbols / len(symbol_returns) * 100, 2
        ) if symbol_returns else 0.0,
        "maximum_drawdown_pct": round(max(drawdowns), 4) if drawdowns else 0.0,
        "total_trades": total_trades,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "symbol_returns_pct": symbol_returns,
    }


def _development_pass(summary: Dict[str, Any]) -> bool:
    profit_factor = summary.get("profit_factor")
    return all(
        [
            summary["median_return_pct"] > 0,
            summary["positive_cell_rate_pct"] >= 60,
            summary["positive_symbol_rate_pct"] >= 60,
            profit_factor is not None and profit_factor >= 1.10,
            summary["total_trades"] >= 30,
            summary["maximum_drawdown_pct"] <= 8,
        ]
    )


def _holdout_pass(summary: Dict[str, Any]) -> bool:
    profit_factor = summary.get("profit_factor")
    return all(
        [
            summary["median_return_pct"] > 0,
            summary["positive_symbol_rate_pct"] >= 60,
            profit_factor is not None and profit_factor >= 1.0,
            summary["total_trades"] >= 5,
            summary["maximum_drawdown_pct"] <= 8,
        ]
    )


def _development_score(summary: Dict[str, Any]) -> float:
    profit_factor = float(summary.get("profit_factor") or 0)
    return round(
        summary["median_return_pct"]
        + 0.25 * summary["average_return_pct"]
        + 0.03 * summary["positive_cell_rate_pct"]
        + 0.03 * summary["positive_symbol_rate_pct"]
        + min(profit_factor, 3.0)
        - 0.15 * summary["maximum_drawdown_pct"],
        6,
    )


def _config_grid() -> List[StrategyConfig]:
    return [
        StrategyConfig(
            threshold=threshold,
            atr_multiplier=atr_multiplier,
            reward_risk=reward_risk,
            max_holding_bars=max_holding_bars,
            relative_strength_filter=relative_strength_filter,
            trend_exit=trend_exit,
        )
        for threshold in (70, 80, 90)
        for atr_multiplier in (1.5, 2.0, 2.5)
        for reward_risk in (1.5, 2.0, 3.0)
        for max_holding_bars in (20, 60)
        for relative_strength_filter in (False, True)
        for trend_exit in (False, True)
    ]


def _load_data(symbols: List[str]) -> Dict[str, Any]:
    payloads: Dict[str, Any] = {}
    for symbol in sorted(set(symbols + ["SPY", "QQQ"])):
        payload = get_daily_bars(
            symbol,
            limit=RESEARCH_BAR_LIMIT,
            lookback_days=RESEARCH_LOOKBACK_DAYS,
        )
        payload["bars"] = _completed_bars(payload.get("bars", []))
        payload["bar_count"] = len(payload["bars"])
        payloads[symbol] = payload
    return payloads


def run_strategy_research(symbols: List[str]) -> Dict[str, Any]:
    started = time.time()
    symbols = sorted({str(symbol).strip().upper() for symbol in symbols if symbol})
    payloads = _load_data(symbols)
    errors = {
        symbol: payload.get("error") or "Insufficient data."
        for symbol, payload in payloads.items()
        if not payload.get("ok") or len(payload.get("bars", [])) < MIN_HISTORY + 240
    }
    if errors:
        return {
            "ok": False,
            "conclusion": "INSUFFICIENT_RESEARCH_DATA",
            "errors": errors,
            "paper_only": True,
        }

    index_series = {
        symbol: _index_series(payloads[symbol]["bars"])
        for symbol in ("SPY", "QQQ")
    }
    prepared: Dict[str, Dict[str, Any]] = {}
    for symbol in symbols:
        bars = payloads[symbol]["bars"]
        folds = _fold_ranges(len(bars))
        if len(folds) != RESEARCH_FOLDS:
            errors[symbol] = "Unable to create four sufficiently large folds."
            continue
        prepared[symbol] = {
            "bars": bars,
            "features": _feature_rows(bars, index_series),
            "folds": folds,
        }
    if errors:
        return {
            "ok": False,
            "conclusion": "INSUFFICIENT_RESEARCH_DATA",
            "errors": errors,
            "paper_only": True,
        }

    ranked: List[Dict[str, Any]] = []
    for config in _config_grid():
        development_cells = []
        holdout_cells = []
        for symbol, data in prepared.items():
            for fold_index, (start_index, end_index) in enumerate(data["folds"]):
                cell = _simulate_fold(
                    symbol,
                    data["bars"],
                    data["features"],
                    start_index,
                    end_index,
                    config,
                )
                cell["fold"] = fold_index + 1
                if fold_index < RESEARCH_FOLDS - 1:
                    development_cells.append(cell)
                else:
                    holdout_cells.append(cell)

        development = _aggregate(development_cells)
        ranked.append(
            {
                "config": asdict(config),
                "development": development,
                "development_pass": _development_pass(development),
                "development_score": _development_score(development),
                "holdout_cells": holdout_cells,
            }
        )

    ranked.sort(
        key=lambda row: (
            bool(row["development_pass"]),
            float(row["development_score"]),
        ),
        reverse=True,
    )

    finalists = []
    for row in ranked[:TOP_RESULT_COUNT]:
        holdout = _aggregate(row.pop("holdout_cells"))
        row["holdout"] = holdout
        row["holdout_pass"] = _holdout_pass(holdout)
        row["robust_candidate"] = bool(
            row["development_pass"] and row["holdout_pass"]
        )
        finalists.append(row)

    leader = finalists[0] if finalists else None
    robust = bool(leader and leader["robust_candidate"])
    conclusion = "ROBUST_CANDIDATE_FOUND" if robust else "NO_ROBUST_EDGE"

    return {
        "ok": True,
        "conclusion": conclusion,
        "paper_only": True,
        "live_strategy_changed": False,
        "method": {
            "lookback_days": RESEARCH_LOOKBACK_DAYS,
            "requested_bars_per_symbol": RESEARCH_BAR_LIMIT,
            "folds": RESEARCH_FOLDS,
            "development_folds": 3,
            "untouched_holdout_folds": 1,
            "configuration_count": len(_config_grid()),
            "selection_uses_holdout": False,
            "execution": "Prior-close signal executed at next open.",
            "slippage_bps_each_side": _slippage_rate() * 10_000,
            "same_bar_stop_and_target": "STOP_FIRST",
        },
        "data": {
            symbol: {
                "bar_count": payloads[symbol]["bar_count"],
                "first_bar": _date_key(payloads[symbol]["bars"][0].get("timestamp")),
                "last_bar": _date_key(payloads[symbol]["bars"][-1].get("timestamp")),
                "feed": payloads[symbol].get("feed"),
                "pages_fetched": payloads[symbol].get("pages_fetched"),
            }
            for symbol in sorted(payloads)
        },
        "leader": leader,
        "top_results": finalists,
        "guardrail": (
            "Do not change the live strategy unless the development-selected leader also passes the untouched holdout and subsequent paper burn-in."
        ),
        "elapsed_seconds": round(time.time() - started, 3),
    }


def install_research(app_module: Any) -> None:
    if getattr(app_module, "_research_installed", False):
        return
    app_module._research_installed = True

    @app_module.app.get("/api/research/strategy-v2")
    def strategy_v2_research(force: bool = False):
        cache_key = ",".join(sorted(app_module.watchlist))
        now = time.time()
        with _cache_lock:
            cached = _research_cache.get(cache_key)
            if (
                not force
                and cached
                and now - cached["cached_at"] < RESEARCH_CACHE_SECONDS
            ):
                response = dict(cached["result"])
                response["cache"] = {
                    "hit": True,
                    "age_seconds": round(now - cached["cached_at"], 2),
                }
                return response

        result = run_strategy_research(list(app_module.watchlist))
        with _cache_lock:
            _research_cache[cache_key] = {
                "cached_at": time.time(),
                "result": result,
            }
        response = dict(result)
        response["cache"] = {"hit": False, "age_seconds": 0}
        return response
