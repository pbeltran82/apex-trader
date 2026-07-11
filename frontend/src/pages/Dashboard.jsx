import "./dashboard.css";
import { useEffect, useState } from "react";

function resolveApiBase() {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  return explicit ? explicit.replace(/\/$/, "") : "/api";
}

const API = resolveApiBase();
const TOKEN_STORAGE_KEY = "kyleOperatorToken";

function getStoredOperatorToken() {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function saveOperatorToken(token) {
  try {
    if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Private browsing or restricted storage can reject localStorage access.
  }
}

async function apiGet(path, fallback = null) {
  try {
    const response = await fetch(`${API}${path}`, { cache: "no-store" });
    if (!response.ok) return fallback;
    return await response.json();
  } catch (error) {
    console.error(`GET ${path} failed:`, error);
    return fallback;
  }
}

async function apiPost(path) {
  let token = getStoredOperatorToken();
  if (!token) {
    token = window.prompt("Enter the Kyle operator token for remote control:")?.trim() || "";
    if (!token) throw new Error("Operator token is required for remote control.");
    saveOperatorToken(token);
  }

  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: {
      "X-Kyle-Operator-Token": token,
    },
  });

  if (response.status === 401) {
    saveOperatorToken("");
    throw new Error("Operator token was rejected. The saved token was cleared.");
  }
  if (response.status === 503) {
    throw new Error(
      "Remote control is disabled until KYLE_OPERATOR_TOKEN is configured on the server.",
    );
  }
  if (!response.ok) {
    throw new Error(`${path} failed with status ${response.status}`);
  }

  const result = await response.json();
  if (result?.ok === false) {
    throw new Error(result.message || `${path} was rejected by Kyle.`);
  }
  return result;
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function formatPct(value, alreadyPercent = false) {
  const number = Number(value || 0);
  return `${(alreadyPercent ? number : number * 100).toFixed(2)}%`;
}

function formatDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
}

function humanize(value) {
  if (!value) return "—";
  return String(value)
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusCopy(status, reason) {
  const normalized = String(status || "IDLE").toUpperCase();
  const titles = {
    RESTORED: "Restored From Disk",
    CYCLE_COMPLETE: "Cycle Complete",
    SHADOW_CYCLE_COMPLETE: "Shadow Cycle Complete",
    RUNNING: "Observer Running",
    STOPPED: "Observer Stopped",
    IDLE: "Idle",
    BLOCKED_RISK_GATE: "Blocked By Risk Gate",
    BLOCKED_STRATEGY_EVIDENCE: "Strategy Evidence Blocked",
    START_REJECTED: "Start Rejected",
    MARKET_CLOSED: "Market Closed",
    MARKET_OPEN: "Market Open",
    STALE_MARKET_DATA: "Stale Market Data",
    MARKET_DATA_UNAVAILABLE: "Market Data Unavailable",
    MAX_POSITIONS: "Max Positions Reached",
    NO_CANDIDATE: "No Trade Candidate",
    REJECTED: "Signal Rejected",
    ERROR: "Error",
  };
  const fallbackReasons = {
    RESTORED: "System state was restored from disk.",
    CYCLE_COMPLETE: "The latest guarded cycle completed.",
    SHADOW_CYCLE_COMPLETE: "The latest hypothetical trading cycle completed.",
    RUNNING: "Kyle is running observation and hypothetical execution cycles.",
    STOPPED: "The autonomous observer is stopped.",
    IDLE: "Kyle is waiting for an operator command.",
    MARKET_CLOSED: "Kyle is waiting for the next valid market session.",
    BLOCKED_STRATEGY_EVIDENCE: "Normal autonomous entries remain blocked.",
  };
  return {
    title: titles[normalized] || humanize(normalized),
    reason: reason || fallbackReasons[normalized] || "Waiting for Kyle status.",
  };
}

function StatusDot({ ok, warning = false }) {
  const tone = warning ? "amber" : ok ? "green" : "red";
  return <span className={`dot ${tone}`} />;
}

function Badge({ tone = "neutral", children }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

const RISK_COPY = {
  drawdown_guard: "Shadow drawdown is within the configured ceiling.",
  position_concentration_guard: "Largest hypothetical position is within limit.",
  cash_guard: "The shadow portfolio retains the required cash buffer.",
  daily_trade_limit: "Hypothetical trade count remains below the daily limit.",
  daily_loss_guard: "Shadow daily loss remains within the shutdown threshold.",
  consecutive_loss_guard: "Consecutive shadow losses remain within limit.",
  total_open_risk_guard: "Total hypothetical stop risk remains within limit.",
};

function RiskCheck({ name, passed }) {
  return (
    <div className="risk-check">
      <div>
        <strong>{humanize(name)}</strong>
        <p>{RISK_COPY[name] || "Shadow risk control status."}</p>
      </div>
      <Badge tone={passed ? "good" : "bad"}>{passed ? "PASS" : "BLOCK"}</Badge>
    </div>
  );
}

function PortfolioPosition({ position, shadow = false }) {
  return (
    <div className="position-row">
      <div>
        <strong>{position.symbol}</strong>
        <small>{shadow ? "Hypothetical" : "Actual paper"}</small>
      </div>
      <span>{position.qty} shares</span>
      <span>{formatMoney(position.market_value)}</span>
      <span>{formatPct(position.unrealized_pnl_pct, true)}</span>
      {shadow && (
        <span className="position-levels">
          Stop {formatMoney(position.stop_loss)} · Target {formatMoney(position.take_profit)}
        </span>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [coo, setCoo] = useState(null);
  const [shadow, setShadow] = useState(null);
  const [market, setMarket] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  async function loadCoreDashboard() {
    const [cooData, shadowData] = await Promise.all([
      apiGet("/coo/status"),
      apiGet("/shadow"),
    ]);
    setCoo(cooData);
    setShadow(shadowData);
    setLastUpdated(new Date());
    setLastError(
      cooData && shadowData ? null : `Unable to reach all backend services through ${API}`,
    );
  }

  async function loadMarketStatus() {
    const marketData = await apiGet("/market-data/status");
    if (marketData) setMarket(marketData);
  }

  async function postAction(path, confirmation = null) {
    if (confirmation && !window.confirm(confirmation)) return;
    setActionLoading(true);
    try {
      await apiPost(path);
      await Promise.all([loadCoreDashboard(), loadMarketStatus()]);
      setLastError(null);
    } catch (error) {
      console.error("Action failed:", error);
      setLastError(error.message);
    } finally {
      setActionLoading(false);
    }
  }

  useEffect(() => {
    loadCoreDashboard();
    loadMarketStatus();
    const coreTimer = setInterval(loadCoreDashboard, 5000);
    const marketTimer = setInterval(loadMarketStatus, 60000);
    return () => {
      clearInterval(coreTimer);
      clearInterval(marketTimer);
    };
  }, []);

  const readiness = coo?.readiness;
  const mission = coo?.mission_control;
  const status = readiness?.autonomous_status || mission?.status;
  const actualAccount = shadow?.actual_paper_account || mission?.account;
  const actualPositions = mission?.positions || [];
  const actualTrades = Number(shadow?.actual_paper_trades ?? mission?.recent_trades?.length ?? 0);
  const recentDecisions = mission?.recent_decisions || [];

  const shadowEnabled = Boolean(shadow?.enabled);
  const realOrdersDisabled = shadow?.real_orders_allowed === false;
  const shadowPositions = shadow?.positions || [];
  const shadowTrades = shadow?.trades || [];
  const shadowPerformance = shadow?.performance;
  const shadowRisk = shadow?.risk;
  const strategy = shadow?.strategy_validation;
  const strategyValidated = Boolean(strategy?.passed);

  const marketGate = market?.gate;
  const marketStatus = marketGate?.status || status?.last_status || "UNKNOWN";
  const marketAllowed = Boolean(marketGate?.allowed);
  const readableStatus = statusCopy(status?.last_status, status?.last_reason);
  const backendOnline = Boolean(coo && shadow && !lastError);
  const safetyReady = backendOnline && shadowEnabled && realOrdersDisabled;
  const actualAccountUntouched =
    Number(shadow?.actual_paper_positions || 0) === 0 && actualTrades === 0;

  return (
    <main className="kyle-page">
      <section className="hero">
        <div>
          <p className="eyebrow">Kyle Apex Trader</p>
          <h1>
            <StatusDot ok={safetyReady} warning={backendOnline && !safetyReady} />
            {lastError ? "Backend Offline" : "Shadow Operations Console"}
          </h1>
          <p className="subline">
            {lastError ||
              "Live market observation and hypothetical execution with actual orders disabled."}
          </p>
        </div>
        <button
          className="danger-button"
          disabled={actionLoading}
          onClick={() => postAction("/autonomous-trader/stop")}
        >
          Emergency Stop
        </button>
      </section>

      <section className="status-strip" aria-label="Critical safety status">
        <div>
          <span>Mode</span>
          <Badge tone={shadowEnabled ? "shadow" : "warn"}>
            {shadowEnabled ? "SHADOW" : "DISABLED"}
          </Badge>
        </div>
        <div>
          <span>Real Orders</span>
          <Badge tone={realOrdersDisabled ? "good" : "bad"}>
            {realOrdersDisabled ? "DISABLED" : "UNKNOWN"}
          </Badge>
        </div>
        <div>
          <span>Strategy</span>
          <Badge tone={strategyValidated ? "good" : "warn"}>
            {strategy?.status || "UNKNOWN"}
          </Badge>
        </div>
        <div>
          <span>Market</span>
          <Badge tone={marketAllowed ? "good" : marketStatus === "MARKET_CLOSED" ? "neutral" : "warn"}>
            {humanize(marketStatus)}
          </Badge>
        </div>
        <div>
          <span>Actual Positions</span>
          <Badge tone={Number(shadow?.actual_paper_positions || 0) === 0 ? "good" : "bad"}>
            {shadow?.actual_paper_positions ?? actualPositions.length}
          </Badge>
        </div>
      </section>

      <section className="safety-banner">
        <strong>No paper or live orders will be submitted in shadow mode.</strong>
        <span>
          All entries and exits shown below are hypothetical. The actual paper account must remain unchanged.
        </span>
      </section>

      {lastError && <section className="error-banner">{lastError}</section>}

      <section className="panel control-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Operator Control</p>
            <h2>Shadow Observer</h2>
          </div>
          <Badge tone={status?.running ? "good" : "neutral"}>
            {status?.running ? "RUNNING" : "STOPPED"}
          </Badge>
        </div>

        <div className="control-copy">
          <strong>{readableStatus.title}</strong>
          <p>{readableStatus.reason}</p>
        </div>

        <div className="coo-actions">
          {!shadowEnabled && (
            <button disabled={actionLoading} onClick={() => postAction("/shadow/enable")}>
              Enable Shadow Mode
            </button>
          )}
          <button
            className="primary-button"
            disabled={actionLoading || !shadowEnabled || status?.running}
            onClick={() => postAction("/autonomous-trader/start")}
          >
            Start Shadow Observer
          </button>
          <button
            disabled={actionLoading || !shadowEnabled}
            onClick={() => postAction("/shadow/run")}
          >
            Run One Shadow Cycle
          </button>
          <button
            disabled={actionLoading || !status?.running}
            onClick={() => postAction("/autonomous-trader/stop")}
          >
            Stop Observer
          </button>
          <button
            className="outline-button"
            disabled={actionLoading}
            onClick={() =>
              postAction(
                "/shadow/reset",
                "Reset the entire hypothetical shadow portfolio and stop the observer?",
              )
            }
          >
            Reset Shadow Ledger
          </button>
          <button
            disabled={actionLoading}
            onClick={() => {
              saveOperatorToken("");
              setLastError(
                "Saved operator token cleared. The next control action will request it again.",
              );
            }}
          >
            Change Token
          </button>
        </div>

        {!strategyValidated && (
          <div className="blocked-control-note">
            <Badge tone="bad">NORMAL PAPER ENTRIES BLOCKED</Badge>
            <span>{strategy?.message || "The active strategy has not passed evidence review."}</span>
          </div>
        )}
      </section>

      <section className="grid portfolio-comparison">
        <section className="panel shadow-panel">
          <div className="panel-header compact">
            <div>
              <p className="eyebrow">Simulation</p>
              <h2>Shadow Portfolio</h2>
            </div>
            <Badge tone="shadow">HYPOTHETICAL</Badge>
          </div>
          <div className="portfolio-hero-value">{formatMoney(shadow?.equity)}</div>
          <div className="row"><span>Cash</span><strong>{formatMoney(shadow?.cash)}</strong></div>
          <div className="row"><span>Total P/L</span><strong>{formatMoney(shadowPerformance?.total_pnl)}</strong></div>
          <div className="row"><span>Return</span><strong>{formatPct(shadowPerformance?.return_pct, true)}</strong></div>
          <div className="row"><span>Hypothetical Positions</span><strong>{shadowPositions.length}</strong></div>
          <div className="row"><span>Hypothetical Trades</span><strong>{shadowPerformance?.trade_count ?? shadowTrades.length}</strong></div>
          <div className="row"><span>Win Rate</span><strong>{formatPct(shadowPerformance?.win_rate_pct, true)}</strong></div>
        </section>

        <section className={`panel actual-panel ${actualAccountUntouched ? "safe-account" : "account-alert"}`}>
          <div className="panel-header compact">
            <div>
              <p className="eyebrow">Protected Account</p>
              <h2>Actual Paper Account</h2>
            </div>
            <Badge tone={actualAccountUntouched ? "good" : "bad"}>
              {actualAccountUntouched ? "UNTOUCHED" : "CHANGED"}
            </Badge>
          </div>
          <div className="portfolio-hero-value">{formatMoney(actualAccount?.equity)}</div>
          <div className="row"><span>Balance</span><strong>{formatMoney(actualAccount?.balance)}</strong></div>
          <div className="row"><span>Buying Power</span><strong>{formatMoney(actualAccount?.buying_power)}</strong></div>
          <div className="row"><span>Actual Positions</span><strong>{shadow?.actual_paper_positions ?? actualPositions.length}</strong></div>
          <div className="row"><span>Actual Trades</span><strong>{actualTrades}</strong></div>
          <div className="row"><span>Real Orders Allowed</span><strong>{realOrdersDisabled ? "NO" : "UNKNOWN"}</strong></div>
          <p className="note">This account must remain unchanged throughout shadow observation.</p>
        </section>
      </section>

      <section className="grid operational-grid">
        <section className="panel">
          <div className="panel-header compact">
            <h2>Market Gate</h2>
            <Badge tone={marketAllowed ? "good" : marketStatus === "MARKET_CLOSED" ? "neutral" : "warn"}>
              {humanize(marketStatus)}
            </Badge>
          </div>
          <p className="note market-reason">
            {marketGate?.reason || "Waiting for a verified market-clock response."}
          </p>
          <div className="row"><span>Clock Source</span><strong>{marketGate?.clock?.source || "—"}</strong></div>
          <div className="row"><span>Next Open</span><strong>{formatDateTime(marketGate?.clock?.next_open)}</strong></div>
          <div className="row"><span>Quote Age Limit</span><strong>{marketGate?.max_quote_age_seconds ?? "—"} sec</strong></div>
          <div className="row"><span>Data Sources</span><strong>{market?.refresh?.sources?.join(", ") || "—"}</strong></div>
          <div className="row"><span>Missing Quotes</span><strong>{marketGate?.missing_symbols?.length ?? 0}</strong></div>
          <div className="row"><span>Stale Quotes</span><strong>{marketGate?.stale_symbols?.length ?? 0}</strong></div>
        </section>

        <section className="panel strategy-panel">
          <div className="panel-header compact">
            <h2>Strategy Evidence</h2>
            <Badge tone={strategyValidated ? "good" : "bad"}>
              {strategyValidated ? "APPROVED" : "BLOCKED"}
            </Badge>
          </div>
          <div className="strategy-status">{strategy?.status || "UNKNOWN"}</div>
          <p className="note">{strategy?.message || "Waiting for strategy validation status."}</p>
          <div className="row"><span>Required Status</span><strong>{humanize(strategy?.required_status)}</strong></div>
          <div className="row"><span>Automatic Approval</span><strong>{strategy?.automatic_approval ? "YES" : "NO"}</strong></div>
          <div className="row"><span>Normal Entries</span><strong>{strategyValidated ? "ELIGIBLE" : "DISABLED"}</strong></div>
        </section>
      </section>

      <section className="panel risk-panel">
        <div className="panel-header compact">
          <div>
            <p className="eyebrow">Shadow Controls</p>
            <h2>Risk Guardrails</h2>
          </div>
          <Badge tone={shadowRisk?.ready ? "good" : "bad"}>
            {shadowRisk?.ready ? "READY" : "BLOCKED"}
          </Badge>
        </div>
        <section className="risk-list">
          {Object.entries(shadowRisk?.checks || {}).map(([name, passed]) => (
            <RiskCheck name={name} passed={Boolean(passed)} key={name} />
          ))}
        </section>
        <section className="grid risk-metrics">
          <div className="metric-card"><span>Cash Buffer</span><strong>{formatPct(shadowRisk?.metrics?.cash_pct)}</strong></div>
          <div className="metric-card"><span>Drawdown</span><strong>{formatPct(shadowRisk?.metrics?.drawdown_pct)}</strong></div>
          <div className="metric-card"><span>Open Risk</span><strong>{formatPct(shadowRisk?.metrics?.open_risk_pct)}</strong></div>
          <div className="metric-card"><span>Consecutive Losses</span><strong>{shadowRisk?.metrics?.consecutive_losses ?? 0}</strong></div>
        </section>
      </section>

      <section className="grid lower-grid">
        <section className="panel">
          <div className="panel-header compact">
            <h2>Shadow Positions</h2>
            <Badge tone="shadow">{shadowPositions.length}</Badge>
          </div>
          {shadowPositions.length === 0 ? (
            <p className="note">No hypothetical positions are open.</p>
          ) : (
            shadowPositions.map((position) => (
              <PortfolioPosition position={position} shadow key={position.symbol} />
            ))
          )}
        </section>

        <section className="panel">
          <div className="panel-header compact">
            <h2>Actual Paper Positions</h2>
            <Badge tone={actualPositions.length === 0 ? "good" : "bad"}>{actualPositions.length}</Badge>
          </div>
          {actualPositions.length === 0 ? (
            <p className="note">No actual paper positions. This is the required shadow-test state.</p>
          ) : (
            actualPositions.map((position) => (
              <PortfolioPosition position={position} key={position.symbol} />
            ))
          )}
        </section>
      </section>

      <section className="grid lower-grid">
        <section className="panel">
          <h2>Recent Shadow Trades</h2>
          {shadowTrades.length === 0 ? (
            <p className="note">No hypothetical trades have been recorded.</p>
          ) : (
            shadowTrades.slice(-8).reverse().map((trade) => (
              <div className="timeline-item" key={`shadow-${trade.id}-${trade.timestamp}`}>
                <span>{formatDateTime(trade.timestamp)}</span>
                <p>
                  <strong>{trade.side} {trade.symbol}</strong> · {trade.qty} shares at {formatMoney(trade.price)} · Real order: NO
                </p>
              </div>
            ))
          )}
        </section>

        <section className="panel">
          <h2>Recent System Decisions</h2>
          {recentDecisions.length === 0 ? (
            <p className="note">No recent decisions are available.</p>
          ) : (
            recentDecisions.slice(-8).reverse().map((item, index) => (
              <div className="timeline-item" key={item.id || item.timestamp || index}>
                <span>{formatDateTime(item.timestamp)}</span>
                <p>{humanize(item.event_type || item.action || "Activity Logged")}</p>
              </div>
            ))
          )}
        </section>
      </section>

      <footer>
        API: {API} · Mode: {shadowEnabled ? "shadow" : "disabled"} · Observer: {status?.running ? "running" : "stopped"} · Updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
      </footer>
    </main>
  );
}
