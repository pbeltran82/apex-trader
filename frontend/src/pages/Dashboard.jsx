import "./dashboard.css";
import { useEffect, useState } from "react";

const API = "/api";

function formatMoney(value) {
  const number = Number(value || 0);
  return number.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

function StatusDot({ ok }) {
  return <span className={ok ? "dot green" : "dot red"} />;
}

export default function Dashboard() {
  const [executive, setExecutive] = useState(null);
  const [operations, setOperations] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [burnIn, setBurnIn] = useState(null);
  const [timeline, setTimeline] = useState([]);

  async function loadDashboard() {
    try {
      const [
        executiveData,
        operationsData,
        readinessData,
        burnInData,
        timelineData,
      ] = await Promise.all([
        fetch(`${API}/executive-dashboard`).then((r) => r.json()),
        fetch(`${API}/operations-dashboard`).then((r) => r.json()),
        fetch(`${API}/readiness-report`).then((r) => r.json()),
        fetch(`${API}/burn-in`).then((r) => r.json()),
        fetch(`${API}/timeline`).then((r) => r.json()).catch(() => []),
      ]);

      setExecutive(executiveData);
      setOperations(operationsData);
      setReadiness(readinessData);
      setBurnIn(burnInData);
      setTimeline(Array.isArray(timelineData) ? timelineData : []);
    } catch (error) {
      console.error("Dashboard load failed:", error);
    }
  }

  useEffect(() => {
    loadDashboard();
    const timer = setInterval(loadDashboard, 5000);
    return () => clearInterval(timer);
  }, []);

  const mission = executive?.briefing;
  const portfolio = executive?.mission_control?.portfolio;
  const health = executive?.health;
  const recommendation = executive?.mission_control?.recommendation;
  const opsHealthy = operations?.system_status === "HEALTHY";
  const readyForPaper = readiness?.paper_trading_ready;

  return (
    <main className="kyle-page">
      <section className="hero">
        <div>
          <p className="eyebrow">Kyle</p>
          <h1>
            <StatusDot ok={opsHealthy} />
            {mission?.status || "Loading"}
          </h1>
          <p className="subline">
            {readyForPaper ? "Ready for Paper Trading" : "Not Ready"}
          </p>
        </div>

        <button className="danger-button">Emergency Stop</button>
      </section>

      <section className="grid">
        <section className="panel">
          <h2>Mission</h2>
          <div className="row">
            <span>Priority</span>
            <strong>{mission?.headline || "Loading..."}</strong>
          </div>
          <div className="row">
            <span>Mode</span>
            <strong>{mission?.mode || "—"}</strong>
          </div>
          <div className="row">
            <span>Autopilot</span>
            <strong>{mission?.autopilot || "—"}</strong>
          </div>
          <p className="note">{mission?.briefing || "Kyle is loading mission data."}</p>
        </section>

        <section className="panel">
          <h2>Portfolio</h2>
          <div className="metric">
            <span>Cash</span>
            <strong>{formatMoney(portfolio?.cash)}</strong>
          </div>
          <div className="metric">
            <span>Equity</span>
            <strong>{formatMoney(portfolio?.equity)}</strong>
          </div>
          <div className="row">
            <span>Exposure</span>
            <strong>{portfolio?.exposure_pct ?? 0}%</strong>
          </div>
          <div className="row">
            <span>Positions</span>
            <strong>{portfolio?.open_positions ?? 0}</strong>
          </div>
        </section>

        <section className="panel">
          <h2>Recommendation</h2>
          <h3>{recommendation?.action || "No action required"}</h3>
          <p className="note">
            {recommendation?.message || "Kyle is monitoring the market."}
          </p>
        </section>

        <section className="panel">
          <h2>System</h2>
          <div className="row">
            <span>Health</span>
            <strong>{operations?.system_status || "Loading"}</strong>
          </div>
          <div className="row">
            <span>Broker</span>
            <strong>
              {operations?.broker?.connected ? "Connected" : "Disconnected"}
            </strong>
          </div>
          <div className="row">
            <span>Burn-In</span>
            <strong>{burnIn?.running ? "Running" : "Stopped"}</strong>
          </div>
          <div className="row">
            <span>Readiness</span>
            <strong>{readiness?.overall_status || "—"}</strong>
          </div>
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
       Trading Performance: {health?.grade || "—"} / {health?.status || "—"}
      </footer>
    </main>
  );
}