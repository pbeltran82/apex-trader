import { useEffect, useState } from "react";

const API = "/api";

export default function RiskGovernorPanel() {
  const [risk, setRisk] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadRisk = async () => {
    try {
      const data = await fetch(`${API}/risk-governor/status`).then((r) =>
        r.json()
      );
      setRisk(data);
    } catch (err) {
      console.error("RISK GOVERNOR ERROR:", err);
    }
  };

  const emergencyStop = async () => {
    setLoading(true);
    try {
      await fetch(`${API}/risk-governor/stop`, { method: "POST" });
      await loadRisk();
    } finally {
      setLoading(false);
    }
  };

  const resumeTrading = async () => {
    setLoading(true);
    try {
      await fetch(`${API}/risk-governor/resume`, { method: "POST" });
      await loadRisk();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRisk();
    const id = setInterval(loadRisk, 5000);
    return () => clearInterval(id);
  }, []);

  if (!risk) return null;

  return (
    <section className="panel risk-governor-panel">
      <div className="panel-header">
        <h2>Risk Governor</h2>
        <span className={risk.safe ? "positive" : "negative"}>
          {risk.safe ? "SAFE" : "SHUTDOWN"}
        </span>
      </div>

      <div className="risk-grid">
        <div>
          <span>Total P/L</span>
          <strong className={risk.total_pnl >= 0 ? "positive" : "negative"}>
            ${Number(risk.total_pnl || 0).toFixed(2)}
          </strong>
        </div>

        <div>
          <span>Realized P/L</span>
          <strong className={risk.realized_pnl >= 0 ? "positive" : "negative"}>
            ${Number(risk.realized_pnl || 0).toFixed(2)}
          </strong>
        </div>

        <div>
          <span>Exposure</span>
          <strong>{Number(risk.exposure_pct || 0).toFixed(2)}%</strong>
        </div>

        <div>
          <span>Open Positions</span>
          <strong>{risk.open_positions}</strong>
        </div>

        <div>
          <span>Loss Limit</span>
          <strong>${risk.limits.daily_loss_limit}</strong>
        </div>

        <div>
          <span>Max Exposure</span>
          <strong>{risk.limits.max_exposure_pct}%</strong>
        </div>
      </div>

      {risk.reason && <p className="risk-reason">{risk.reason}</p>}

      <div className="risk-actions">
        <button className="risk-stop-button" onClick={emergencyStop}>
          {loading ? "Working..." : "Emergency Stop"}
        </button>

        <button className="risk-resume-button" onClick={resumeTrading}>
          Resume
        </button>
      </div>
    </section>
  );
}