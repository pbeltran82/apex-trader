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
    throw new Error("Remote control is disabled until KYLE_OPERATOR_TOKEN is configured on the server.");
  }
  if (!response.ok) {
    throw new Error(`${path} failed with status ${response.status}`);
  }
  return response.json();
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
    RUNNING: "Running",
    STOPPED: "Stopped",
    IDLE: "Idle",
    BLOCKED_RISK_GATE: "Blocked By Risk Gate",
    MARKET_CLOSED: "Market Closed",
    STALE_MARKET_DATA: "Stale Market Data",
    MARKET_DATA_UNAVAILABLE: "Market Data Unavailable",
    MAX_POSITIONS: "Max Positions Reached",
    NO_CANDIDATE: "No Trade Candidate",
    REJECTED: "Trade Rejected",
    ERROR: "Error",
  };
  const fallbackReasons = {
    RESTORED: "Paper portfolio restored from disk.",
    CYCLE_COMPLETE: "The latest guarded paper-trading cycle completed.",
    RUNNING: "Kyle is actively running autonomous paper-trading cycles.",
    STOPPED: "Autonomous paper trading is stopped.",
    IDLE: "Kyle is waiting for an operator command.",
    MARKET_CLOSED: "Kyle is waiting for the next valid market session.",
  };
  return {
    title: titles[normalized] || humanize(normalized),
    reason: reason || fallbackReasons[normalized] || "Waiting for Kyle status.",
  };
}

function recommendationCopy(action, running) {
  if (running) {
    return {
      title: "Autonomous Trader Running",
      message: "Kyle is operating the paper-trading loop under the active market and risk gates.",
    };
  }
  if (action === "start_autonomous_trader") {
    return {
      title: "Start Autonomous Trader",
      message: "Kyle is ready for autonomous paper-trading cycles.",
    };
  }
  if (action === "hold_or_review_blockers") {
    return {
      title: "Review Risk Blockers",
      message: "Kyle is paused until the active readiness blockers are resolved.",
    };
  }
  return {
    title: action ? humanize(action) : "No Action Required",
    message: "Kyle is monitoring risk, storage, positions, and paper-trading decisions.",
  };
}

function StatusDot({ ok }) {
  return <span className={ok ? "dot green" : "dot red"} />;
}

function RiskCheck({ check }) {
  return (
    <div className="risk-check">
      <div>
        <strong>{humanize(check.name)}</strong>
        <p>{check.message}</p>
      </div>
      <span className={check.passed ? "pill good" : "pill bad"}>
        {check.passed ? "PASS" : "BLOCK"}
      </span>
    </div>
  );
}

export default function Dashboard() {
  const [coo, setCoo] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [lastError, setLastError] = useState(null);

  async function loadDashboard() {
    const cooData = await apiGet("/coo/status");
    setCoo(cooData);
    setLastError(cooData ? null : `Unable to reach backend through ${API}`);
  }

  async function postAction(path) {
    setActionLoading(true);
    try {
      await apiPost(path);
      await loadDashboard();
      setLastError(null);
    } catch (error) {
      console.error("Action failed:", error);
      setLastError(error.message);
    } finally {
      setActionLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
    const timer = setInterval(loadDashboard, 5000);
    return () => clearInterval(timer);
  }, []);

  const readiness = coo?.readiness;
  const mission = coo?.mission_control;
  const status = readiness?.autonomous_status;
  const risk = readiness?.risk;
  const performance = mission?.performance;
  const account = mission?.account;
  const positions = mission?.positions || [];
  const recentDecisions = mission?.recent_decisions || [];
  const recentTrades = mission?.recent_trades || [];
  const readyForPaper = Boolean(readiness?.ready_for_autonomous_paper_trading);
  const healthy = Boolean(risk?.ready && coo);
  const readableStatus = statusCopy(status?.last_status, status?.last_reason);
  const recommendation = recommendationCopy(readiness?.next_best_action, status?.running);

  return (
    <main className="kyle-page">
      <section className="hero">
        <div>
          <p className="eyebrow">Kyle Apex Trader</p>
          <h1>
            <StatusDot ok={healthy} />
            {lastError ? "Backend Offline" : recommendation.title}
          </h1>
          <p className="subline">
            {readyForPaper ? "Ready for Autonomous Paper Trading" : lastError || "Not Ready"}
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

      <section className="panel coo-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">COO Control</p>
            <h2>Autonomous Paper Trader</h2>
          </div>
          <span className={risk?.ready ? "pill good" : "pill bad"}>
            {risk?.ready ? "READY" : "BLOCKED"}
          </span>
        </div>

        <div className="coo-actions">
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/start")}>Start</button>
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/run-guarded")}>Run Guarded Cycle</button>
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/stop")}>Stop</button>
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/liquidate")}>Liquidate Paper</button>
          <button
            disabled={actionLoading}
            onClick={() => {
              saveOperatorToken("");
              setLastError("Saved operator token cleared. The next control action will request it again.");
            }}
          >
            Change Token
          </button>
        </div>

        <section className="grid coo-grid">
          <div className="metric-card">
            <span>Status</span>
            <strong>{readableStatus.title}</strong>
            <p>{readableStatus.reason}</p>
          </div>
          <div className="metric-card">
            <span>Equity</span>
            <strong>{formatMoney(account?.equity)}</strong>
            <p>Cash: {formatMoney(account?.buying_power)}</p>
          </div>
          <div className="metric-card">
            <span>Return</span>
            <strong>{formatPct(performance?.return_pct, true)}</strong>
            <p>Total P/L: {formatMoney(performance?.total_pnl)}</p>
          </div>
          <div className="metric-card">
            <span>Trades</span>
            <strong>{performance?.trade_count ?? 0}</strong>
            <p>Win rate: {formatPct(performance?.win_rate, true)}</p>
          </div>
        </section>

        <section className="risk-list">
          {(risk?.checks || []).map((check) => <RiskCheck check={check} key={check.name} />)}
        </section>
      </section>

      <section className="grid">
        <section className="panel">
          <h2>Mission</h2>
          <div className="row"><span>Mode</span><strong>{mission?.mode || "paper"}</strong></div>
          <div className="row"><span>Autopilot</span><strong>{status?.running ? "Running" : "Stopped"}</strong></div>
          <div className="row"><span>Cycles</span><strong>{status?.cycles ?? 0}</strong></div>
          <p className="note">{recommendation.message}</p>
        </section>

        <section className="panel">
          <h2>Portfolio</h2>
          <div className="metric"><span>Cash</span><strong>{formatMoney(account?.buying_power)}</strong></div>
          <div className="metric"><span>Equity</span><strong>{formatMoney(account?.equity)}</strong></div>
          <div className="row"><span>Cash %</span><strong>{formatPct(risk?.metrics?.cash_pct)}</strong></div>
          <div className="row"><span>Positions</span><strong>{positions.length}</strong></div>
        </section>

        <section className="panel">
          <h2>Risk Limits</h2>
          <div className="row"><span>Max Drawdown</span><strong>{formatPct(risk?.limits?.max_drawdown_pct)}</strong></div>
          <div className="row"><span>Max Concentration</span><strong>{formatPct(risk?.limits?.max_position_concentration_pct)}</strong></div>
          <div className="row"><span>Minimum Cash</span><strong>{formatPct(risk?.limits?.min_cash_pct)}</strong></div>
          <div className="row"><span>Daily Trade Limit</span><strong>{risk?.limits?.max_daily_trades ?? 0}</strong></div>
        </section>

        <section className="panel">
          <h2>System</h2>
          <div className="row"><span>Health</span><strong>{healthy ? "HEALTHY" : "BLOCKED"}</strong></div>
          <div className="row"><span>State File</span><strong>{readiness?.storage?.state_file_exists ? "Persisting" : "Waiting"}</strong></div>
          <div className="row"><span>Decision Log</span><strong>{readiness?.storage?.decision_log_file_exists ? "Persisting" : "Waiting"}</strong></div>
          <div className="row"><span>Readiness</span><strong>{readyForPaper ? "READY" : "NOT READY"}</strong></div>
        </section>
      </section>

      <section className="grid lower-grid">
        <section className="panel">
          <h2>Positions</h2>
          {positions.length === 0 ? <p className="note">No open paper positions.</p> : positions.map((position) => (
            <div className="position-row" key={position.symbol}>
              <strong>{position.symbol}</strong>
              <span>{position.qty} shares</span>
              <span>{formatMoney(position.market_value)}</span>
              <span>{formatPct(position.unrealized_pnl_pct, true)}</span>
            </div>
          ))}
        </section>

        <section className="panel">
          <h2>Recent Activity</h2>
          {[...recentDecisions, ...recentTrades].length === 0 ? (
            <p className="note">No recent paper-trading activity.</p>
          ) : (
            [...recentDecisions, ...recentTrades].slice(-6).reverse().map((item, index) => (
              <div className="timeline-item" key={item.id || item.timestamp || index}>
                <span>{item.timestamp || "—"}</span>
                <p>{humanize(item.event_type || item.action || item.side || "Activity Logged")}</p>
              </div>
            ))
          )}
        </section>
      </section>

      <footer>
        API: {API} · Mode: {mission?.mode || "paper"} · Status: {readableStatus.title}
      </footer>
    </main>
  );
}
