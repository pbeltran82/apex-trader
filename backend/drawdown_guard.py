from backend.portfolio_live import build_portfolio_live

_state = {
    "peak_equity": None,
}


def get_drawdown_status():
    portfolio = build_portfolio_live()
    equity = float(portfolio.get("equity", 0) or 0)

    if _state["peak_equity"] is None:
        _state["peak_equity"] = equity

    if equity > _state["peak_equity"]:
        _state["peak_equity"] = equity

    peak = _state["peak_equity"] or equity or 1

    drawdown_pct = round(
        ((peak - equity) / peak) * 100,
        2,
    )

    return {
        "equity": round(equity, 2),
        "peak_equity": round(peak, 2),
        "drawdown_pct": drawdown_pct,
    }


def reset_peak_equity():
    portfolio = build_portfolio_live()
    equity = float(portfolio.get("equity", 0) or 0)

    _state["peak_equity"] = equity

    return get_drawdown_status()