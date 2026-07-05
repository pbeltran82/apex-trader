import { useEffect, useState } from "react";

const API = "/api";

export default function AutoExitPanel() {
  const [status, setStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const [autoRun, setAutoRun] = useState(false);

  const loadStatus = async () => {
    try {
      const data = await fetch(`${API}/auto-exit/status`).then((r) =>
        r.json()
      );
      setStatus(data);
    } catch (err) {
      console.error("AUTO EXIT STATUS ERROR:", err);
    }
  };

  const runAutoExit = async () => {
    setRunning(true);

    try {
      await fetch(`${API}/auto-exit/run`, {
        method: "POST",
      });

      await loadStatus();
    } catch (err) {
      console.error("AUTO EXIT RUN ERROR:", err);
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

    const id = setInterval(runAutoExit, 5000);

    return () => clearInterval(id);
  }, [autoRun]);

  if (!status) return null;

  return (
    <section className="panel auto-exit-panel">
      <div className="panel-header">
        <h2>Auto Exit Manager</h2>
        <span>{status.enabled ? "Enabled" : "Disabled"}</span>
      </div>

      <div className="auto-exit-grid">
        <div>
          <span>Watching</span>
          <strong>{status.watching_positions}</strong>
        </div>

        <div>
          <span>Checks</span>
          <strong>{status.checks}</strong>
        </div>

        <div>
          <span>Take Profit</span>
          <strong>{status.take_profit_pct}%</strong>
        </div>

        <div>
          <span>Stop Loss</span>
          <strong>{status.stop_loss_pct}%</strong>
        </div>
      </div>

      <div className="auto-exit-controls">
        <button className="auto-exit-button" onClick={runAutoExit}>
          {running ? "Checking..." : "Run Exit Check"}
        </button>

        <button
          className={`auto-exit-auto-button ${autoRun ? "active" : ""}`}
          onClick={() => setAutoRun((value) => !value)}
        >
          {autoRun ? "Auto Exit ON" : "Auto Exit OFF"}
        </button>
      </div>

      {status.last_exit ? (
        <div className="auto-exit-last">
          <strong>Last Exit</strong>
          <p>
            {status.last_exit.symbol} sold at ${status.last_exit.price}. P/L $
            {status.last_exit.realized_pnl}
          </p>
        </div>
      ) : (
        <p className="auto-exit-muted">No auto exits yet.</p>
      )}
    </section>
  );
}