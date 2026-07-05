import { useEffect, useState } from "react";

const API = "/api";

export default function AutopilotPanel() {
  const [status, setStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const [autoRun, setAutoRun] = useState(false);

  const loadStatus = async () => {
    try {
      const data = await fetch(`${API}/autopilot/status`).then((r) =>
        r.json()
      );
      setStatus(data);
    } catch (err) {
      console.error("AUTOPILOT STATUS ERROR:", err);
    }
  };

  const startAutopilot = async () => {
    setRunning(true);
    try {
      await fetch(`${API}/autopilot/start`, { method: "POST" });
      await loadStatus();
    } finally {
      setRunning(false);
    }
  };

  const stopAutopilot = async () => {
    setRunning(true);
    try {
      setAutoRun(false);
      await fetch(`${API}/autopilot/stop`, { method: "POST" });
      await loadStatus();
    } finally {
      setRunning(false);
    }
  };

  const runCycle = async () => {
    setRunning(true);
    try {
      const res = await fetch(`${API}/autopilot/run`, { method: "POST" });
      const data = await res.json();

      if (data?.action === "RISK_SHUTDOWN") {
        setAutoRun(false);
      }

      await loadStatus();
    } catch (err) {
      console.error("AUTOPILOT RUN ERROR:", err);
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const id = setInterval(loadStatus, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!autoRun) return;

    const id = setInterval(runCycle, 15000);

    return () => clearInterval(id);
  }, [autoRun]);

  if (!status) return null;

  return (
    <section className="panel autopilot-panel">
      <div className="panel-header">
        <h2>Autopilot</h2>
        <span className={status.enabled ? "positive" : "negative"}>
          {status.enabled ? "ENABLED" : "DISABLED"}
        </span>
      </div>

      <div className="autopilot-grid">
        <div>
          <span>Cycles</span>
          <strong>{status.cycles}</strong>
        </div>

        <div>
          <span>Mode</span>
          <strong>{autoRun ? "AUTO" : "MANUAL"}</strong>
        </div>

        <div>
          <span>Last Trade</span>
          <strong>{status.last_trade || "None"}</strong>
        </div>

        <div>
          <span>Last Action</span>
          <strong>{status.last_action || "Waiting"}</strong>
        </div>
      </div>

      {status.last_error && (
        <p className="autopilot-error">{status.last_error}</p>
      )}

      <div className="autopilot-actions">
        <button onClick={startAutopilot} className="autopilot-start">
          Start
        </button>

        <button onClick={runCycle} className="autopilot-run">
          {running ? "Running..." : "Run Cycle"}
        </button>

        <button
          onClick={() => setAutoRun((value) => !value)}
          className={`autopilot-auto ${autoRun ? "active" : ""}`}
        >
          {autoRun ? "Auto ON" : "Auto OFF"}
        </button>

        <button onClick={stopAutopilot} className="autopilot-stop">
          Stop
        </button>
      </div>
    </section>
  );
}