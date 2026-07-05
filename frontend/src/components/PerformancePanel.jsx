import { useEffect, useState } from "react";

const API = "/api";

export default function PerformancePanel() {
  const [performance, setPerformance] = useState(null);
  const [stats, setStats] = useState(null);

  const load = async () => {
    try {
      const [performanceData, statsData] = await Promise.all([
        fetch(`${API}/performance`).then((r) => r.json()),
        fetch(`${API}/trade-stats`).then((r) => r.json()),
      ]);

      setPerformance(performanceData);
      setStats(statsData);
    } catch (err) {
      console.error("PERFORMANCE ERROR:", err);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  if (!performance) return null;

  const money = (value) =>
    Number(value || 0).toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
    });

  const pnlClass = (value) => (Number(value) >= 0 ? "positive" : "negative");

  return (
    <section className="panel performance-panel">
      <div className="panel-header">
        <h2>Performance Analytics</h2>
        <span>{performance.return_pct}% Return</span>
      </div>

      <div className="performance-grid">
        <div>
          <span>Equity</span>
          <strong>{money(performance.current_equity)}</strong>
        </div>

        <div>
          <span>Cash</span>
          <strong>{money(performance.cash)}</strong>
        </div>

        <div>
          <span>Total P/L</span>
          <strong className={pnlClass(performance.total_pnl)}>
            {money(performance.total_pnl)}
          </strong>
        </div>

        <div>
          <span>Realized P/L</span>
          <strong className={pnlClass(stats?.realized_pnl ?? 0)}>
            {money(stats?.realized_pnl ?? 0)}
          </strong>
        </div>

        <div>
          <span>Unrealized P/L</span>
          <strong className={pnlClass(performance.unrealized_pnl)}>
            {money(performance.unrealized_pnl)}
          </strong>
        </div>

        <div>
          <span>Exposure</span>
          <strong>{Number(performance.exposure_pct || 0).toFixed(2)}%</strong>
        </div>

        <div>
          <span>Total Trades</span>
          <strong>{stats?.total_trades ?? performance.total_trades}</strong>
        </div>

        <div>
          <span>Closed Trades</span>
          <strong>{stats?.closed_trades ?? 0}</strong>
        </div>

        <div>
          <span>Buy Trades</span>
          <strong>{stats?.buy_trades ?? performance.buy_trades}</strong>
        </div>

        <div>
          <span>Sell Trades</span>
          <strong>{stats?.sell_trades ?? performance.sell_trades}</strong>
        </div>

        <div>
          <span>Open Positions</span>
          <strong>{performance.open_positions}</strong>
        </div>

        <div>
          <span>Win Rate</span>
          <strong>{Number(stats?.win_rate ?? 0).toFixed(2)}%</strong>
        </div>
      </div>

      <p className="performance-summary">{performance.summary}</p>
    </section>
  );
}