from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional

from api.historical_data import get_daily_bars
from api.intelligence import _atr, _clamp, _completed_bars, _pct_change, _sma


STARTING_EQUITY = 10_000.0
MIN_HISTORY = 205
MAX_HOLDING_BARS = 30


def _date_key(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value)[:10]


def _slippage_rate() -> float:
    raw = os.getenv("KYLE_BACKTEST_SLIPPAGE_BPS", "5")
    try:
        basis_points = _clamp(float(raw), 0, 100)
    except ValueError:
        basis_points = 5
    return basis_points / 10_000


def _regime_at(index_bars: Dict[str, List[Dict[str, Any]]], signal_date: str) -> Dict[str, Any]:
    score = 0.0
    diagnostics = []
    for symbol, bars in index_bars.items():
        usable = [bar for bar in bars if _date_key(bar.get("timestamp")) <= signal_date]
        if len(usable) < 200:
            diagnostics.append({"symbol": symbol, "ok": False, "bar_count": len(usable)})
            continue
        closes = [float(bar["close"]) for bar in usable]
        price = closes[-1]
        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)
        return20 = _pct_change(price, closes[-21])
        component = 0.0
        component += 2.5 if price > sma50 else 0
        component += 2.5 if sma50 > sma200 else 0
        component += 2.5 if return20 > 0 else 0
        score += component
        diagnostics.append(
            {
                "symbol": symbol,
                "ok": True,
                "price": round(price, 2),
                "sma50": round(float(sma50), 2),
                "sma200": round(float(sma200), 2),
                "return20_pct": round(return20 * 100, 2),
                "score": component,
            }
        )

    if len([row for row in diagnostics if row.get("ok")]) < 2:
        return {
            "regime": "UNKNOWN",
            "score": 0.0,
            "trade_allowed": False,
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
        "score": round(score, 2),
        "trade_allowed": allowed,
        "indexes": diagnostics,
    }


def _signal(history: List[Dict[str, Any]], index_bars: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    if len(history) < MIN_HISTORY:
        return {"approved": False, "score": 0, "reason": "Insufficient history."}

    closes = [float(bar["close"]) for bar in history]
    volumes = [float(bar.get("volume") or 0) for bar in history]
    price = closes[-1]
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    atr14 = _atr(history, 14)
    if None in (sma20, sma50, sma200, atr14):
        return {"approved": False, "score": 0, "reason": "Indicators unavailable."}

    return20 = _pct_change(price, closes[-21])
    return60 = _pct_change(price, closes[-61])
    average_volume20 = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 0
    volume_ratio = volumes[-1] / average_volume20 if average_volume20 else 1.0
    atr_pct = float(atr14) / price if price else 0.0

    trend_score = 0.0
    trend_score += 8 if price > sma20 else 0
    trend_score += 8 if sma20 > sma50 else 0
    trend_score += 8 if sma50 > sma200 else 0
    trend_score += 6 if price > sma200 else 0
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

    signal_date = _date_key(history[-1].get("timestamp"))
    regime = _regime_at(index_bars, signal_date)
    score = int(
        round(
            _clamp(
                trend_score
                + momentum_score
                + volume_score
                + volatility_score
                + regime["score"],
                0,
                100,
            )
        )
    )
    threshold = 75 if regime["regime"] == "MIXED" else 70
    hard_filters = {
        "market_regime_trade_allowed": regime["trade_allowed"],
        "price_above_sma50": price > sma50,
        "sma50_above_sma200": sma50 > sma200,
        "positive_20d_momentum": return20 > 0,
    }
    stop_pct = _clamp(atr_pct * 1.5, 0.02, 0.08)
    take_profit_pct = _clamp(stop_pct * 2.0, 0.03, 0.20)
    approved = all(hard_filters.values()) and score >= threshold

    return {
        "approved": approved,
        "score": score,
        "threshold": threshold,
        "price": price,
        "sma50": float(sma50),
        "stop_loss_pct": stop_pct,
        "take_profit_pct": take_profit_pct,
        "atr14": float(atr14),
        "return20_pct": return20 * 100,
        "return60_pct": return60 * 100,
        "volume_ratio20": volume_ratio,
        "regime": regime,
        "hard_filters": hard_filters,
    }


def _max_drawdown(equity_curve: List[Dict[str, Any]]) -> float:
    peak = 0.0
    maximum = 0.0
    for point in equity_curve:
        equity = float(point["equity"])
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak)
    return maximum


def backtest_symbol(symbol: str) -> Dict[str, Any]:
    symbol = str(symbol).strip().upper()
    symbol_payload = get_daily_bars(symbol, limit=500)
    bars = _completed_bars(symbol_payload.get("bars", []))
    index_payloads = {
        index: _completed_bars(get_daily_bars(index, limit=500).get("bars", []))
        for index in ("SPY", "QQQ")
    }

    if len(bars) < MIN_HISTORY + 2:
        return {
            "ok": False,
            "symbol": symbol,
            "error": "Insufficient completed historical bars for walk-forward testing.",
            "bar_count": len(bars),
            "required": MIN_HISTORY + 2,
        }
    if any(len(index_bars) < MIN_HISTORY for index_bars in index_payloads.values()):
        return {
            "ok": False,
            "symbol": symbol,
            "error": "Insufficient SPY/QQQ history for regime-aware testing.",
        }

    cash = STARTING_EQUITY
    position: Optional[Dict[str, Any]] = None
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    slippage = _slippage_rate()
    cooldown_until_index = -1

    for index in range(MIN_HISTORY, len(bars)):
        bar = bars[index]
        history = bars[:index]
        signal = _signal(history, index_payloads)
        date = _date_key(bar.get("timestamp"))

        if position is not None:
            position["holding_bars"] += 1
            exit_price = None
            exit_reason = None
            day_open = float(bar["open"])
            day_low = float(bar["low"])
            day_high = float(bar["high"])

            # When both levels are touched intraday, assume the stop was hit
            # first. This deliberately avoids optimistic ordering assumptions.
            if day_low <= position["stop_loss"]:
                exit_price = min(day_open, position["stop_loss"])
                exit_reason = "STOP_LOSS"
            elif day_high >= position["take_profit"]:
                exit_price = max(day_open, position["take_profit"])
                exit_reason = "TAKE_PROFIT"
            elif not signal.get("hard_filters", {}).get("price_above_sma50", True):
                exit_price = day_open
                exit_reason = "TREND_BREAK"
            elif position["holding_bars"] >= MAX_HOLDING_BARS:
                exit_price = day_open
                exit_reason = "TIME_EXIT"

            if exit_price is not None:
                adjusted_exit = float(exit_price) * (1 - slippage)
                proceeds = position["qty"] * adjusted_exit
                cash += proceeds
                pnl = proceeds - position["cost"]
                trades.append(
                    {
                        "entry_date": position["entry_date"],
                        "exit_date": date,
                        "qty": position["qty"],
                        "entry_price": round(position["entry_price"], 4),
                        "exit_price": round(adjusted_exit, 4),
                        "pnl": round(pnl, 2),
                        "return_pct": round((adjusted_exit / position["entry_price"] - 1) * 100, 2),
                        "exit_reason": exit_reason,
                        "entry_score": position["entry_score"],
                        "holding_bars": position["holding_bars"],
                    }
                )
                position = None
                cooldown_until_index = index + 1

        if position is None and index > cooldown_until_index and signal.get("approved"):
            entry_price = float(bar["open"]) * (1 + slippage)
            equity = cash
            risk_budget = equity * 0.005
            per_share_risk = entry_price * signal["stop_loss_pct"]
            qty_by_risk = int(risk_budget // per_share_risk) if per_share_risk > 0 else 0
            qty_by_notional = int((equity * 0.15) // entry_price)
            qty_by_cash = int(cash // entry_price)
            qty = min(qty_by_risk, qty_by_notional, qty_by_cash)
            if qty > 0:
                cost = qty * entry_price
                cash -= cost
                position = {
                    "qty": qty,
                    "entry_date": date,
                    "entry_price": entry_price,
                    "cost": cost,
                    "stop_loss": entry_price * (1 - signal["stop_loss_pct"]),
                    "take_profit": entry_price * (1 + signal["take_profit_pct"]),
                    "entry_score": signal["score"],
                    "holding_bars": 0,
                }

        marked_equity = cash
        if position is not None:
            marked_equity += position["qty"] * float(bar["close"])
        equity_curve.append({"date": date, "equity": round(marked_equity, 2)})

    if position is not None:
        last_bar = bars[-1]
        adjusted_exit = float(last_bar["close"]) * (1 - slippage)
        proceeds = position["qty"] * adjusted_exit
        cash += proceeds
        pnl = proceeds - position["cost"]
        trades.append(
            {
                "entry_date": position["entry_date"],
                "exit_date": _date_key(last_bar.get("timestamp")),
                "qty": position["qty"],
                "entry_price": round(position["entry_price"], 4),
                "exit_price": round(adjusted_exit, 4),
                "pnl": round(pnl, 2),
                "return_pct": round((adjusted_exit / position["entry_price"] - 1) * 100, 2),
                "exit_reason": "END_OF_TEST",
                "entry_score": position["entry_score"],
                "holding_bars": position["holding_bars"],
            }
        )
        equity_curve.append(
            {
                "date": _date_key(last_bar.get("timestamp")),
                "equity": round(cash, 2),
            }
        )

    wins = [trade for trade in trades if trade["pnl"] > 0]
    losses = [trade for trade in trades if trade["pnl"] < 0]
    gross_profit = sum(trade["pnl"] for trade in wins)
    gross_loss = abs(sum(trade["pnl"] for trade in losses))
    ending_equity = round(cash, 2)
    total_return = (ending_equity / STARTING_EQUITY - 1) * 100
    buy_hold_return = (
        (float(bars[-1]["close"]) / float(bars[MIN_HISTORY]["open"]) - 1) * 100
    )

    return {
        "ok": True,
        "symbol": symbol,
        "method": "NO_LOOKAHEAD_WALK_FORWARD",
        "paper_only": True,
        "assumptions": {
            "starting_equity": STARTING_EQUITY,
            "risk_per_trade_pct": 0.5,
            "maximum_position_pct": 15.0,
            "reward_risk_ratio": 2.0,
            "maximum_holding_bars": MAX_HOLDING_BARS,
            "slippage_bps_each_side": round(slippage * 10_000, 2),
            "same_bar_stop_and_target": "STOP_FIRST",
            "execution": "Signal on prior close; execute at next open.",
        },
        "period": {
            "start": _date_key(bars[MIN_HISTORY].get("timestamp")),
            "end": _date_key(bars[-1].get("timestamp")),
            "bars_tested": len(bars) - MIN_HISTORY,
        },
        "performance": {
            "ending_equity": ending_equity,
            "total_return_pct": round(total_return, 2),
            "buy_hold_return_pct": round(buy_hold_return, 2),
            "excess_return_pct": round(total_return - buy_hold_return, 2),
            "max_drawdown_pct": round(_max_drawdown(equity_curve) * 100, 2),
            "trade_count": len(trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate_pct": round((len(wins) / len(trades) * 100), 2) if trades else 0.0,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
            "average_trade_return_pct": round(
                sum(trade["return_pct"] for trade in trades) / len(trades), 2
            ) if trades else 0.0,
        },
        "trades": trades,
        "equity_curve": equity_curve,
    }


def install_backtester(app_module: Any) -> None:
    if getattr(app_module, "_backtester_installed", False):
        return
    app_module._backtester_installed = True

    @app_module.app.get("/api/backtest/{symbol}")
    def run_symbol_backtest(symbol: str):
        return backtest_symbol(symbol)
