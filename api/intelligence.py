from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
import threading
import time
from typing import Any, Dict, List, Optional

from api.historical_data import get_daily_bars


SECTOR_MAP = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Semiconductors",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
}
REGIME_SYMBOLS = ("SPY", "QQQ")
MINIMUM_HISTORY_BARS = 205

_cache_lock = threading.Lock()
_bars_cache: Dict[str, Dict[str, Any]] = {}
_regime_cache: Dict[str, Any] = {}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _cache_seconds() -> int:
    raw = os.getenv("KYLE_INTELLIGENCE_CACHE_SECONDS", "900")
    try:
        return max(60, int(raw))
    except ValueError:
        return 900


def _risk_per_trade_pct() -> float:
    raw = os.getenv("KYLE_RISK_PER_TRADE_PCT", "0.005")
    try:
        return _clamp(float(raw), 0.001, 0.02)
    except ValueError:
        return 0.005


def _reward_risk_ratio() -> float:
    raw = os.getenv("KYLE_REWARD_RISK_RATIO", "2.0")
    try:
        return _clamp(float(raw), 1.0, 4.0)
    except ValueError:
        return 2.0


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _completed_bars(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    completed = []
    for bar in bars:
        observed = _parse_timestamp(bar.get("timestamp"))
        if observed is not None and observed.date() >= today:
            continue
        completed.append(bar)
    return completed


def _load_bars(symbol: str) -> Dict[str, Any]:
    symbol = str(symbol).strip().upper()
    now = time.time()
    ttl = _cache_seconds()

    with _cache_lock:
        cached = _bars_cache.get(symbol)
        if cached and now - cached["cached_at"] < ttl:
            return deepcopy(cached["payload"])

    payload = get_daily_bars(symbol, limit=260)
    payload["bars"] = _completed_bars(payload.get("bars", []))
    payload["bar_count"] = len(payload["bars"])
    payload["ok"] = bool(payload["bars"])

    with _cache_lock:
        _bars_cache[symbol] = {"cached_at": now, "payload": deepcopy(payload)}

    return payload


def _sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _pct_change(current: float, reference: float) -> float:
    if not reference:
        return 0.0
    return (current - reference) / reference


def _atr(bars: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    if len(bars) < period + 1:
        return None
    true_ranges = []
    for index in range(1, len(bars)):
        current = bars[index]
        previous = bars[index - 1]
        high = float(current["high"])
        low = float(current["low"])
        previous_close = float(previous["close"])
        true_ranges.append(
            max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
    recent = true_ranges[-period:]
    return sum(recent) / len(recent) if recent else None


def _technical_snapshot(symbol: str, current_price: float) -> Dict[str, Any]:
    history = _load_bars(symbol)
    bars = history.get("bars", [])
    if len(bars) < MINIMUM_HISTORY_BARS:
        return {
            "ok": False,
            "symbol": symbol,
            "bar_count": len(bars),
            "required_bars": MINIMUM_HISTORY_BARS,
            "source": history.get("source"),
            "error": history.get("error") or "Insufficient completed daily bars.",
        }

    closes = [float(bar["close"]) for bar in bars]
    volumes = [float(bar.get("volume") or 0) for bar in bars]
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    atr14 = _atr(bars, 14)

    if None in (sma20, sma50, sma200, atr14):
        return {
            "ok": False,
            "symbol": symbol,
            "bar_count": len(bars),
            "error": "Required indicators could not be calculated.",
        }

    return20 = _pct_change(current_price, closes[-21])
    return60 = _pct_change(current_price, closes[-61])
    average_volume20 = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 0
    latest_completed_volume = volumes[-1]
    volume_ratio = latest_completed_volume / average_volume20 if average_volume20 else 1.0
    atr_pct = atr14 / current_price if current_price else 0.0

    trend_score = 0.0
    trend_score += 8 if current_price > sma20 else 0
    trend_score += 8 if sma20 > sma50 else 0
    trend_score += 8 if sma50 > sma200 else 0
    trend_score += 6 if current_price > sma200 else 0

    momentum_score = _clamp(
        12.5 + (return20 * 100 * 0.8) + (return60 * 100 * 0.25),
        0,
        25,
    )
    volume_score = _clamp(7.5 + ((volume_ratio - 1.0) * 7.5), 0, 15)

    atr_pct_points = atr_pct * 100
    if 1.0 <= atr_pct_points <= 4.0:
        volatility_score = 15.0
    elif 0.5 <= atr_pct_points <= 5.5:
        volatility_score = 11.0
    elif atr_pct_points <= 7.0:
        volatility_score = 7.0
    else:
        volatility_score = 3.0

    return {
        "ok": True,
        "symbol": symbol,
        "source": history.get("source"),
        "bar_count": len(bars),
        "last_completed_bar": bars[-1].get("timestamp"),
        "sma20": round(sma20, 4),
        "sma50": round(sma50, 4),
        "sma200": round(sma200, 4),
        "return20_pct": round(return20 * 100, 2),
        "return60_pct": round(return60 * 100, 2),
        "volume_ratio20": round(volume_ratio, 2),
        "atr14": round(atr14, 4),
        "atr_pct": round(atr_pct * 100, 2),
        "scores": {
            "trend": round(trend_score, 2),
            "momentum": round(momentum_score, 2),
            "volume": round(volume_score, 2),
            "volatility": round(volatility_score, 2),
        },
    }


def market_regime(app_module: Any) -> Dict[str, Any]:
    now = time.time()
    ttl = _cache_seconds()
    with _cache_lock:
        cached_at = _regime_cache.get("cached_at", 0)
        if _regime_cache.get("payload") and now - cached_at < ttl:
            return deepcopy(_regime_cache["payload"])

    indexes = []
    regime_score = 0.0
    for symbol in REGIME_SYMBOLS:
        current_price = float(app_module.prices.get(symbol) or 0)
        history = _load_bars(symbol)
        bars = history.get("bars", [])
        if len(bars) < MINIMUM_HISTORY_BARS:
            indexes.append(
                {
                    "symbol": symbol,
                    "ok": False,
                    "bar_count": len(bars),
                    "error": history.get("error") or "Insufficient history.",
                }
            )
            continue

        closes = [float(bar["close"]) for bar in bars]
        price = current_price or closes[-1]
        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)
        return20 = _pct_change(price, closes[-21])
        component = 0.0
        component += 2.5 if price > sma50 else 0
        component += 2.5 if sma50 > sma200 else 0
        component += 2.5 if return20 > 0 else 0
        regime_score += component
        indexes.append(
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

    available = [row for row in indexes if row.get("ok")]
    if len(available) < len(REGIME_SYMBOLS):
        payload = {
            "regime": "UNKNOWN",
            "score": 0.0,
            "trade_allowed": False,
            "reason": "Major-index history is incomplete; Kyle is failing closed.",
            "indexes": indexes,
        }
    elif regime_score >= 12.5:
        payload = {
            "regime": "BULLISH",
            "score": round(regime_score, 2),
            "trade_allowed": True,
            "reason": "SPY and QQQ show broad positive trend and momentum.",
            "indexes": indexes,
        }
    elif regime_score >= 7.5:
        payload = {
            "regime": "MIXED",
            "score": round(regime_score, 2),
            "trade_allowed": True,
            "reason": "Major-index evidence is mixed; Kyle requires stronger symbol scores.",
            "indexes": indexes,
        }
    else:
        payload = {
            "regime": "RISK_OFF",
            "score": round(regime_score, 2),
            "trade_allowed": False,
            "reason": "Major-index trend and momentum are weak; new long entries are blocked.",
            "indexes": indexes,
        }

    with _cache_lock:
        _regime_cache["cached_at"] = now
        _regime_cache["payload"] = deepcopy(payload)
    return payload


def score_symbol(app_module: Any, symbol: str) -> Dict[str, Any]:
    from api import risk_gate

    symbol = app_module._normalize_symbol(symbol)
    price = float(app_module.prices[symbol])
    open_position = app_module._open_position(symbol)
    technical = _technical_snapshot(symbol, price)
    regime = market_regime(app_module)
    risk = risk_gate.risk_telemetry()

    if open_position:
        return {
            "symbol": symbol,
            "sector": SECTOR_MAP.get(symbol, "Unknown"),
            "price": price,
            "action": "HOLD",
            "confidence": 0,
            "score": 0,
            "approved": False,
            "reason": "Kyle already holds this symbol; duplicate entries are blocked.",
            "technical": technical,
            "market_regime": regime,
            "risk": risk,
        }

    if not technical.get("ok"):
        return {
            "symbol": symbol,
            "sector": SECTOR_MAP.get(symbol, "Unknown"),
            "price": price,
            "action": "WAIT",
            "confidence": 0,
            "score": 0,
            "approved": False,
            "reason": "Real historical evidence is unavailable or insufficient.",
            "technical": technical,
            "market_regime": regime,
            "risk": risk,
        }

    components = deepcopy(technical["scores"])
    components["market_regime"] = regime["score"]

    risk_penalty = 0.0
    risk_notes = []
    if not risk["ready"]:
        risk_penalty -= 100
        risk_notes.append("The portfolio risk gate is blocked.")
    if risk["metrics"]["cash_pct"] < 0.25:
        risk_penalty -= 8
        risk_notes.append("Cash is below the preferred 25% buffer.")
    if risk["metrics"]["largest_position_pct"] > 0.20:
        risk_penalty -= 6
        risk_notes.append("Single-position concentration is elevated.")

    sector = SECTOR_MAP.get(symbol, "Unknown")
    same_sector_value = sum(
        float(position.get("market_value", 0))
        for position in app_module.positions
        if SECTOR_MAP.get(position.get("symbol"), "Unknown") == sector
    )
    equity = max(float(app_module.account.get("equity", 0)), 1.0)
    same_sector_pct = same_sector_value / equity
    if same_sector_pct >= 0.25:
        risk_penalty -= 10
        risk_notes.append(f"Existing {sector} exposure is at least 25% of equity.")
    elif same_sector_value > 0:
        risk_penalty -= 4
        risk_notes.append(f"The portfolio already has {sector} exposure.")

    components["risk_penalty"] = risk_penalty
    score = int(round(_clamp(sum(components.values()), 0, 100)))

    hard_filters = {
        "risk_gate_ready": bool(risk["ready"]),
        "market_regime_trade_allowed": bool(regime["trade_allowed"]),
        "price_above_sma50": price > technical["sma50"],
        "sma50_above_sma200": technical["sma50"] > technical["sma200"],
        "positive_20d_momentum": technical["return20_pct"] > 0,
    }
    filters_passed = all(hard_filters.values())
    threshold = int(app_module.config["min_confidence"])
    if regime["regime"] == "MIXED":
        threshold = min(100, threshold + 5)

    approved = filters_passed and score >= threshold
    action = "BUY" if approved else ("WATCH" if score >= 55 else "PASS")

    stop_pct = _clamp((technical["atr_pct"] / 100) * 1.5, 0.02, 0.08)
    reward_risk = _reward_risk_ratio()
    take_profit_pct = _clamp(stop_pct * reward_risk, 0.03, 0.20)

    failed_filters = [name for name, passed in hard_filters.items() if not passed]
    reason_parts = [
        f"Real-data score {score}/{threshold}.",
        f"20-day return {technical['return20_pct']}% and 60-day return {technical['return60_pct']}%.",
        f"ATR {technical['atr_pct']}% with volume ratio {technical['volume_ratio20']}.",
        regime["reason"],
    ]
    if failed_filters:
        reason_parts.append("Blocked filters: " + ", ".join(failed_filters) + ".")
    if risk_notes:
        reason_parts.append(" ".join(risk_notes))

    return {
        "symbol": symbol,
        "sector": sector,
        "price": round(price, 2),
        "action": action,
        "confidence": score,
        "score": score,
        "approved": approved,
        "threshold": threshold,
        "reason": " ".join(reason_parts),
        "components": components,
        "hard_filters": hard_filters,
        "technical": technical,
        "market_regime": regime,
        "portfolio_context": {
            "same_sector_exposure_pct": round(same_sector_pct * 100, 2),
            "cash_pct": risk["metrics"]["cash_pct"],
            "largest_position_pct": risk["metrics"]["largest_position_pct"],
        },
        "risk_model": {
            "risk_per_trade_pct": _risk_per_trade_pct(),
            "stop_loss_pct": round(stop_pct, 4),
            "take_profit_pct": round(take_profit_pct, 4),
            "reward_risk_ratio": reward_risk,
            "atr14": technical["atr14"],
        },
    }


def install_intelligence(app_module: Any) -> None:
    if getattr(app_module, "_intelligence_installed", False):
        return

    def intelligent_score(symbol: str) -> Dict[str, Any]:
        return score_symbol(app_module, symbol)

    def risk_sized_buy(candidate: Dict[str, Any]) -> Dict[str, Any]:
        if not candidate.get("approved"):
            return {"ok": False, "message": "Candidate is not approved by the intelligence engine."}

        symbol = app_module._normalize_symbol(candidate["symbol"])
        if app_module._open_position(symbol):
            return {"ok": False, "message": f"Kyle already holds {symbol}."}
        if len(app_module.positions) >= app_module.config["max_open_positions"]:
            return {"ok": False, "message": "Risk check failed: maximum open positions reached."}

        price = float(candidate["price"])
        risk_model = candidate.get("risk_model", {})
        stop_pct = float(risk_model.get("stop_loss_pct") or app_module.config["stop_loss_pct"])
        take_profit_pct = float(
            risk_model.get("take_profit_pct") or app_module.config["take_profit_pct"]
        )
        equity = max(float(app_module.account.get("equity", 0)), 1.0)
        buying_power = float(app_module.account.get("buying_power", 0))
        risk_budget = equity * float(risk_model.get("risk_per_trade_pct") or _risk_per_trade_pct())
        per_share_risk = price * stop_pct

        qty_by_risk = int(risk_budget // per_share_risk) if per_share_risk > 0 else 0
        qty_by_notional = int(float(app_module.config["max_position_value"]) // price)
        qty_by_cash = int(buying_power // price)
        qty = min(qty_by_risk, qty_by_notional, qty_by_cash)

        if qty <= 0:
            return {
                "ok": False,
                "message": "Risk-based sizing rejected the trade because no safe whole-share quantity is available.",
                "sizing": {
                    "qty_by_risk": qty_by_risk,
                    "qty_by_notional": qty_by_notional,
                    "qty_by_cash": qty_by_cash,
                    "risk_budget": round(risk_budget, 2),
                },
            }

        notional = round(qty * price, 2)
        initial_risk = round(qty * per_share_risk, 2)
        app_module.account["balance"] = round(app_module.account["balance"] - notional, 2)
        position = {
            "symbol": symbol,
            "qty": qty,
            "entry_price": round(price, 2),
            "current_price": round(price, 2),
            "market_value": notional,
            "opened_at": app_module._now(),
            "stop_loss": round(price * (1 - stop_pct), 2),
            "take_profit": round(price * (1 + take_profit_pct), 2),
            "stop_loss_pct": round(stop_pct, 4),
            "take_profit_pct": round(take_profit_pct, 4),
            "risk_budget": round(risk_budget, 2),
            "initial_risk": initial_risk,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "signal_snapshot": {
                "score": candidate.get("score"),
                "threshold": candidate.get("threshold"),
                "components": deepcopy(candidate.get("components", {})),
                "hard_filters": deepcopy(candidate.get("hard_filters", {})),
                "technical": deepcopy(candidate.get("technical", {})),
                "market_regime": deepcopy(candidate.get("market_regime", {})),
            },
        }
        app_module.positions.append(position)
        trade = app_module._record_trade(symbol, "BUY", qty, price, candidate["reason"])
        app_module._refresh_equity()
        app_module._save_state()
        return {
            "ok": True,
            "message": "Risk-sized paper buy executed.",
            "position": position,
            "trade": trade,
            "sizing": {
                "qty_by_risk": qty_by_risk,
                "qty_by_notional": qty_by_notional,
                "qty_by_cash": qty_by_cash,
                "risk_budget": round(risk_budget, 2),
                "initial_risk": initial_risk,
            },
        }

    def position_level_manager() -> List[Dict[str, Any]]:
        updates = []
        app_module._refresh_positions()
        for position in list(app_module.positions):
            symbol = position["symbol"]
            current_price = float(app_module.prices.get(symbol, position["entry_price"]))
            entry_price = float(position["entry_price"])
            stop_loss = float(
                position.get("stop_loss")
                or entry_price * (1 - app_module.config["stop_loss_pct"])
            )
            take_profit = float(
                position.get("take_profit")
                or entry_price * (1 + app_module.config["take_profit_pct"])
            )

            exit_reason = None
            if current_price <= stop_loss:
                exit_reason = "Autonomous position-level stop loss triggered."
            elif current_price >= take_profit:
                exit_reason = "Autonomous position-level take profit triggered."

            if exit_reason:
                result = app_module._sell_position(symbol, exit_reason)
                change_pct = ((current_price - entry_price) / entry_price) * 100
                updates.append({**result, "pnl_pct": round(change_pct, 2)})
        return updates

    app_module._score_symbol = intelligent_score
    app_module._place_paper_buy = risk_sized_buy
    app_module._manage_positions = position_level_manager
    app_module._intelligence_installed = True

    @app_module.app.get("/api/intelligence/score/{symbol}")
    def intelligence_score(symbol: str):
        normalized = app_module._normalize_symbol(symbol)
        if normalized not in app_module.prices:
            return {"ok": False, "message": f"{normalized} is not in Kyle's price universe."}
        return app_module._score_symbol(normalized)

    @app_module.app.get("/api/intelligence/regime")
    def intelligence_regime():
        return market_regime(app_module)

    @app_module.app.post("/api/intelligence/cache/clear")
    def clear_intelligence_cache():
        with _cache_lock:
            _bars_cache.clear()
            _regime_cache.clear()
        return {"ok": True, "message": "Intelligence cache cleared."}
