import { useEffect, useState } from "react";

const API = "/api";

export default function ExecutionQueuePanel() {
  const [queue, setQueue] = useState([]);
  const [running, setRunning] = useState(false);
  const [autoRun, setAutoRun] = useState(false);

  const loadQueue = async () => {
    try {
      const data = await fetch(`${API}/execution-queue`).then((r) => r.json());
      setQueue(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("EXECUTION QUEUE ERROR:", err);
    }
  };

  const runManager = async () => {
    setRunning(true);

    try {
      await fetch(`${API}/execution-manager/run`, {
        method: "POST",
      });

      await loadQueue();
    } catch (err) {
      console.error("EXECUTION MANAGER ERROR:", err);
    } finally {
      setRunning(false);
    }
  };

  const executeTrade = async (symbol) => {
    await fetch(`${API}/execute/${symbol}`, { method: "POST" });
    await loadQueue();
  };

  const completeTrade = async (symbol) => {
    await fetch(`${API}/complete/${symbol}`, { method: "POST" });
    await loadQueue();
  };

  useEffect(() => {
    loadQueue();

    const id = setInterval(loadQueue, 5000);

    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!autoRun) return;

    const id = setInterval(runManager, 5000);

    return () => clearInterval(id);
  }, [autoRun]);

  return (
    <section className="panel execution-panel">
      <div className="panel-header">
        <h2>Execution Queue</h2>
        <span>{queue.length} trades</span>
      </div>

      <div className="execution-controls">
        <button className="execution-run-button" onClick={runManager}>
          {running ? "Running..." : "Run Manager"}
        </button>

        <button
          className={`execution-auto-button ${autoRun ? "active" : ""}`}
          onClick={() => setAutoRun((value) => !value)}
        >
          {autoRun ? "Auto Manager ON" : "Auto Manager OFF"}
        </button>
      </div>

      {queue.length === 0 ? (
        <p className="empty">No queued trades yet.</p>
      ) : (
        <div className="execution-list">
          {queue.map((trade) => (
            <div className="execution-row" key={trade.id}>
              <div>
                <strong>{trade.symbol}</strong>
                <p>{trade.status}</p>

                {trade.message && (
                  <small className="execution-reason">{trade.message}</small>
                )}

                {trade.reason && (
                  <small className="execution-reason">{trade.reason}</small>
                )}

                {trade.attempts && (
                  <small className="execution-attempts">
                    Attempts: {trade.attempts}
                  </small>
                )}
              </div>

              <div className="execution-meta">
                <span>
                  {trade.confidence
                    ? `${Number(trade.confidence).toFixed(0)}%`
                    : "—"}
                </span>

                <small>{trade.shares ? `${trade.shares} sh` : ""}</small>
              </div>

              <div className="execution-actions">
                {trade.status === "WAITING" && (
                  <button onClick={() => executeTrade(trade.symbol)}>
                    Manual
                  </button>
                )}

                {["ACTIVE", "FILLED"].includes(trade.status) && (
                  <button onClick={() => completeTrade(trade.symbol)}>
                    Complete
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}