import "./dashboard.css";
import { useEffect, useState } from "react";

function resolveApiBase() {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (explicit) return explicit.replace(/\/$/, "");

  // Prefer the Vite proxy. In Codespaces, browser access to the exposed 8000
  // backend URL can fail before FastAPI sees the request, while /api through
  // the 5173 Vite server proxies reliably to 127.0.0.1:8000.
  return "/api";
}

const API = resolveApiBase();

async function apiGet(path, fallback = null) {
  try {
    const response = await fetch(`${API}${path}`);
    if (!response.ok) return fallback;
    return await response.json();
  } catch (error) {
    console.error(`GET ${path} failed:`, error);
    return fallback;
  }
}

async function apiPost(path) {
  const response = await fetch(`${API}${path}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`${path} failed with status ${response.status}`);
  }
  return response.json();
}

function formatMoney(value) {
  const number = Number(value || 0);
  return number.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function formatPct(value) {
  const number = Number(value || 0) * 100;
  return `${number.toFixed(2)}%`;
}

function humanize(value) {
  if (!value) return "—";
  const normalized = String(value).replaceAll("_", " ").toLowerCase();
  return normalized.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function recommendationCopy(action, running) {
  const normalized = String(action || "").toLowerCase();

  if (running) {
    return {
      title: "Autonomous Trader Running",
      message: "Kyle is operating the paper-trading loop under the active risk gate.",
    };
  }

  if (normalized === "start_autonomous_trader") {
    return {
      title: "Start Autonomous Trader",
      message: "Kyle is ready. Start the paper-trading loop when you want autonomous cycles to continue in the background.",
    };
  }

  if (normalized === "hold_or_review_blockers") {
    return {
      title: "Review Risk Blockers",
      message: "Kyle is paused because one or more readiness checks needs attention before the next cycle.",
    };
  }

  return {
    title: humanize(action) === "—" ? "No Action Required" : humanize(action),
    message: "Kyle is monitoring readiness, risk, storage, positions, and paper-trading decisions.",
  };
}

function statusCopy(status, reason) {
  const normalized = String(status || "").toUpperCase();

  const titles = {
    RESTORED: "Restored From Disk",
    CYCLE_COMPLETE: "Cycle Complete",
    RUNNING: "Running",
    STOPPED: "Stopped",
    IDLE: "Idle",
    BLOCKED_RISK_GATE: "Blocked By Risk Gate",
    MAX_POSITIONS: "Max Positions Reached",
    NO_CANDIDATE: "No Trade Candidate",
    REJECTED: "Trade Rejected",
    ERROR: "Error",
  };

  const fallbackReasons = {
    RESTORED: "Paper portfolio restored. Start Kyle when you want background autonomous trading.",
    CYCLE_COMPLETE: "Latest guarded cycle completed successfully.",
    RUNNING: "Kyle is actively running autonomous paper cycles.",
    STOPPED: "Autonomous paper trading is stopped.",
    IDLE: "Kyle is waiting for an operator command.",
  };

  return {
    title: titles[normalized] || humanize(status),
    reason: reason || fallbackReasons[normalized] || "Waiting for Kyle status.",
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
  const [executive, setExecutive] = useState(null);
  const [operations, setOperations] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [burnIn, setBurnIn] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [coo, setCoo] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [lastError, setLastError] = useState(null);

  async function loadDashboard() {
    const [
      executiveData,
      operationsData,
      readinessData,
      burnInData,
      timelineData,
      cooData,
    ] = await Promise.all([
      apiGet("/executive-dashboard"),
      apiGet("/operations-dashboard"),
      apiGet("/readiness-report"),
      apiGet("/burn-in"),
      apiGet("/timeline", []),
      apiGet("/coo/status"),
    ]);

    setExecutive(executiveData);
    setOperations(operationsData);
    setReadiness(readinessData);
    setBurnIn(burnInData);
    setTimeline(Array.isArray(timelineData) ? timelineData : []);
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
    console.log("Kyle dashboard API base:", API);
    loadDashboard();
    const timer = setInterval(loadDashboard, 5000);
    return () => clearInterval(timer);
  }, []);

  const mission = executive?.briefing;
  const portfolio = executive?.mission_control?.portfolio;
  const health = executive?.health;
  const recommendation = executive?.mission_control?.recommendation;
  const opsHealthy = operations?.system_status === "HEALTHY" || coo?.readiness?.risk?.ready;
  const readyForPaper = readiness?.paper_trading_ready || coo?.readiness?.ready_for_autonomous_paper_trading;
  const cooReadiness = coo?.readiness;
  const cooMission = coo?.mission_control;
  const cooStatus = cooReadiness?.autonomous_status;
  const cooRisk = cooReadiness?.risk;
  const cooPerformance = cooMission?.performance;
  const positions = cooMission?.positions || [];
  const recentDecisions = cooMission?.recent_decisions || [];
  const readableStatus = statusCopy(cooStatus?.last_status, cooStatus?.last_reason);
  const readableRecommendation = recommendationCopy(
    recommendation?.action || cooReadiness?.next_best_action,
    cooStatus?.running,
  );

  return (
    <main className="kyle-page">
      <section className="hero">
        <div>
          <p className="eyebrow">Kyle</p>
          <h1>
            <StatusDot ok={opsHealthy} />
            {mission?.status || readableRecommendation.title || (lastError ? "Backend Offline" : "Loading")}
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
          <span className={cooRisk?.ready ? "pill good" : "pill bad"}>
            {cooRisk?.ready ? "READY" : "BLOCKED"}
          </span>
        </div>

        <div className="coo-actions">
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/start")}>
            Start
          </button>
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/run-guarded")}>
            Run Guarded Cycle
          </button>
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/stop")}>
            Stop
          </button>
          <button disabled={actionLoading} onClick={() => postAction("/autonomous-trader/liquidate")}>
            Liquidate Paper
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
            <strong>{formatMoney(cooMission?.account?.equity)}</strong>
            <p>Cash: {formatMoney(cooMission?.account?.buying_power)}</p>
          </div>
          <div className="metric-card">
            <span>Return</span>
            <strong>{cooPerformance?.return_pct ?? 0}%</strong>
            <p>Total P/L: {formatMoney(cooPerformance?.total_pnl)}</p>
          </div>
          <div className="metric-card">
            <span>Trades</span>
            <strong>{cooPerformance?.trade_count ?? 0}</strong>
            <p>Win rate: {cooPerformance?.win_rate ?? 0}%</p>
          </div>
        </section>

        <section className="risk-list">
          {(cooRisk?.checks || []).map((check) => (
            <RiskCheck check={check} key={check.name} />
          ))}
        </section>
      </section>

      <section className="grid">
        <section className="panel">
          <h2>Mission</h2>
          <div className="row">
            <span>Priority</span>
            <strong>{mission?.headline || "Autonomous paper-trading burn-in"}</strong>
          </div>
          <div className="row">
            <span>Mode</span>
            <strong>{mission?.mode || cooMission?.mode || "paper"}</strong>
          </div>
          <div className="row">
            <span>Autopilot</span>
            <strong>{mission?.autopilot || (cooStatus?.running ? "Running" : "Stopped")}</strong>
          </div>
          <p className="note">{mission?.briefing || "Kyle is monitoring risk, storage, positions, and autonomous paper cycles."}</p>
        </section>

        <section className="panel">
          <h2>Portfolio</h2>
          <div className="metric">
            <span>Cash</span>
            <strong>{formatMoney(portfolio?.cash ?? cooMission?.account?.buying_power)}</strong>
          </div>
          <div className="metric">
            <span>Equity</span>
            <strong>{formatMoney(portfolio?.equity ?? cooMission?.account?.equity)}</strong>
          </div>
          <div className="row">
            <span>Cash %</span>
            <strong>{formatPct(cooRisk?.metrics?.cash_pct)}</strong>
          </div>
          <div className="row">
            <span>Positions</span>
            <strong>{portfolio?.open_positions ?? positions.length}</strong>
          </div>
        </section>

        <section className="panel">
          <h2>Recommendation</h2>
          <h3>{readableRecommendation.title}</h3>
          <p className="note">
            {recommendation?.message || readableRecommendation.message}
          </p>
        </section>

        <section className="panel">
          <h2>System</h2>
          <div className="row">
            <span>Health</span>
            <strong>{operations?.system_status || (cooRisk?.ready ? "HEALTHY" : "BLOCKED")}</strong>
          </div>
          <div className="row">
            <span>Storage</span>
            <strong>{cooReadiness?.storage?.state_file_exists ? "Persisting" : "Waiting"}</strong>
          </div>
          <div className="row">
            <span>Burn-In</span>
            <strong>{burnIn?.running ? "Running" : "Stopped"}</strong>
          </div>
          <div className="row">
            <span>Readiness</span>
            <strong>{readyForPaper ? "READY" : readiness?.overall_status || "—"}</strong>
          </div>
        </section>
      </section>

      <section className="grid lower-grid">
        <section className="panel">
          <h2>Positions</h2>
          {positions.length === 0 ? (
            <p className="note">No open paper positions.</p>
          ) : (
            positions.map((position) => (
              <div className="position-row" key={position.symbol}>
                <strong>{position.symbol}</strong>
                <span>{position.qty} shares</span>
                <span>{formatMoney(position.market_value)}</span>
                <span>{position.unrealized_pnl_pct ?? 0}%</span>
              </div>
            ))
          )}
        </section>

        <section className="panel">
          <h2>Recent Decisions</h2>
          {recentDecisions.length === 0 ? (
            <p className="note">No recent decision logs.</p>
          ) : (
            recentDecisions.slice(-6).reverse().map((item) => (
              <div className="timeline-item" key={item.id || item.timestamp}>
                <span>{item.timestamp || "—"}</span>
                <p>{humanize(item.event_type || item.action || "Decision Logged")}</p>
              </div>
            ))
          )}
        </section>
      </section>

      <section className="panel timeline">
        <h2>Timeline</h2>

        {timeline.length === 0 ? (
          <p className="note">No recent timeline events. Kyle is monitoring.</p>
        ) : (
          timeline.slice(0, 6).map((item, index) => (
            <div className="timeline-item" key={index}>
              <span>{item.time || item.generated || "—"}</span>
              <p>{item.message || item.type || JSON.stringify(item)}</p>
            </div>
          ))
        )}
      </section>

      <footer>
        API: {API} · Trading Performance: {health?.grade || cooPerformance?.return_pct || "—"} / {health?.status || readableStatus.title || "—"}
      </footer>
    </main>
  );
}
