# Apex Trader

Apex Trader is a personal autonomous paper-trading platform focused on profitability research, disciplined risk management, capital preservation, and progressively greater autonomy with human override.

## Active architecture

The production entry point is `main.py` and the active engine lives in `api/`.

Kyle currently includes:

- Authenticated Alpaca latest-trade market data
- Alpaca market-clock and quote-freshness gating
- Corporate-action-adjusted daily historical bars
- Real SMA trend, 20/60-day momentum, volume, ATR, and SPY/QQQ regime signals
- Risk-based whole-share position sizing
- Position-level ATR stops and reward/risk targets
- Sector and correlated-group projected exposure limits
- Drawdown, cash, concentration, daily-trade, daily-loss, loss-streak, and total-open-risk guards
- Immutable decision events with monotonic IDs
- Re-entry cooldowns after exits
- Persistent paper portfolio and append-only decision history
- Operator-token protection for remote control
- No-lookahead walk-forward backtesting
- A consolidated intelligence readiness report
- Production dashboard controls and emergency stop

## Safety posture

- Paper trading only
- New entries fail closed when the market is closed, quotes are stale, historical evidence is incomplete, the market regime is risk-off, or any active risk/portfolio constraint fails
- Existing positions can be managed under fresh market data even when the entry risk gate is blocked
- Remote write actions require `KYLE_OPERATOR_TOKEN`; direct localhost administration remains available
- Alpaca credentials and runtime data are excluded from Git

## Important endpoints

- `GET /api/intelligence/readiness`
- `GET /api/intelligence/score/{symbol}`
- `GET /api/intelligence/regime`
- `GET /api/market-data/status`
- `GET /api/risk/telemetry`
- `GET /api/risk/advanced`
- `GET /api/portfolio/constraints/{symbol}`
- `GET /api/backtest/{symbol}`
- `POST /api/autonomous-trader/start`
- `POST /api/autonomous-trader/stop`

## Validation

GitHub Actions compiles the active Python modules, runs deterministic intelligence safeguards, installs the locked frontend dependencies, and creates a production Vite build.

Local tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Frontend production build:

```bash
npm ci --prefix frontend
npm run build --prefix frontend
```

## Status

MVP intelligence hardening and paper-validation phase. Live-money execution is intentionally out of scope until walk-forward results and extended paper burn-in demonstrate acceptable risk-adjusted behavior.
