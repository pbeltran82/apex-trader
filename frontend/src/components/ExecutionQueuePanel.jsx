import { useEffect, useState } from "react";

const API = "/api";

export default function ExecutionQueuePanel() {
  const [queue, setQueue] = useState([]);

  const loadQueue = async () => {
    try {
      const data = await fetch(`${API}/execution-queue`).then((r) => r.json());
      setQueue(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("EXECUTION QUEUE ERROR:", err);
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

  return (
    <section className="panel execution-panel">
      <div className="panel-header">
        <h2>Execution Queue</h2>
        <span>{queue.length} trades</span>
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

                {trade.reason && (
                  <small className="execution-reason">{trade.reason}</small>
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
                    Execute
                  </button>
                )}

                {trade.status === "ACTIVE" && (
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