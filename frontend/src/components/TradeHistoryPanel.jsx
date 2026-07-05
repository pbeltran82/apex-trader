import { useEffect, useState } from "react";

const API = "/api";

export default function TradeHistoryPanel() {
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);

  const load = async () => {
    try {
      const [historyData, statsData] = await Promise.all([
        fetch(`${API}/trade-history`).then((r) => r.json()),
        fetch(`${API}/trade-stats`).then((r) => r.json()),
      ]);

      setHistory(Array.isArray(historyData) ? historyData : []);
      setStats(statsData);
    } catch (err) {
      console.error("TRADE HISTORY ERROR:", err);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="panel trade-history-panel">
      <div className="panel-header">
        <h2>Trade History</h2>
        <span>{stats?.total_trades ?? 0} trades</span>
      </div>

      <div className="trade-stats-mini">
        <div>
          <span>Buys</span>
          <strong>{stats?.buy_trades ?? 0}</strong>
        </div>

        <div>
          <span>Sells</span>
          <strong>{stats?.sell_trades ?? 0}</strong>
        </div>

        <div>
          <span>Realized P/L</span>
          <strong>${Number(stats?.realized_pnl ?? 0).toFixed(2)}</strong>
        </div>
      </div>

      {history.length === 0 ? (
        <p className="empty">No trades recorded yet.</p>
      ) : (
        <div className="trade-history-list">
          {history.map((trade) => (
            <div className="trade-history-row" key={trade.id}>
              <div>
                <strong>{trade.symbol}</strong>
                <p>{new Date(trade.time).toLocaleTimeString()}</p>
              </div>

              <span className={trade.side === "BUY" ? "positive" : "negative"}>
                {trade.side}
              </span>

              <span>{trade.qty} sh</span>

              <span>${trade.price}</span>

              <strong>${trade.total}</strong>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}