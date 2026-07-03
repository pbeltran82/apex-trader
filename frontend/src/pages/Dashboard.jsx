import { useEffect, useState } from "react";
import "./dashboard.css";

const API = "/api";

const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

const num = (n) => Number(n ?? 0).toFixed(2);

export default function Dashboard() {
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [prices, setPrices] = useState({});
  const [equity, setEquity] = useState([]);

  const load = async () => {
    try {
      const [a, p, t, pr, e] = await Promise.all([
        fetch(`${API}/account`).then((r) => r.json()),
        fetch(`${API}/positions`).then((r) => r.json()),
        fetch(`${API}/trades`).then((r) => r.json()),
        fetch(`${API}/prices`).then((r) => r.json()),
        fetch(`${API}/equity`).then((r) => r.json()),
      ]);

      setAccount(a);
      setPositions(p);
      setTrades(t);
      setPrices(pr);
      setEquity(e);
    } catch (err) {
      console.error("API ERROR:", err);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 2500);
    return () => clearInterval(id);
  }, []);

  const buy = async (symbol) => {
    await fetch(`${API}/buy/${symbol}`, { method: "POST" });
    load();
  };

  const chartPoints = (() => {
    if (!equity.length) return "";
    const w = 900;
    const h = 260;
    const min = Math.min(...equity.map((x) => x.equity));
    const max = Math.max(...equity.map((x) => x.equity));

    return equity
      .map((x, i) => {
        const px = (i / Math.max(equity.length - 1, 1)) * w;
        const py = h - ((x.equity - min) / (max - min || 1)) * h;
        return `${px},${py}`;
      })
      .join(" ");
  })();

  const totalPnl = positions.reduce((sum, p) => sum + Number(p.pnl ?? 0), 0);

  return (
    <div className="terminal">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">▲</span>
          <span>APEX TRADER</span>
        </div>

        <nav>
          <div className="nav-item active">Dashboard</div>
          <div className="nav-item">Watchlist</div>
          <div className="nav-item">Positions</div>
          <div className="nav-item">Orders</div>
          <div className="nav-item">Analytics</div>
          <div className="nav-item">Settings</div>
        </nav>

        <div className="capital-card">
          <span>Starting Capital</span>
          <strong>$10,000.00</strong>
        </div>
      </aside>

      <main className="content">
        <header className="header">
          <div>
            <h1>Apex Trader <span>Paper Trading</span></h1>
            <p>Simulated execution engine · live paper PnL</p>
          </div>

          <div className="market-pill">
            <span className="pulse"></span>
            Market: Simulated
          </div>
        </header>

        <section className="summary-grid">
          <div className="summary-card">
            <span>Cash</span>
            <strong>{money(account?.balance)}</strong>
          </div>
          <div className="summary-card">
            <span>Equity</span>
            <strong>{money(account?.equity)}</strong>
          </div>
          <div className="summary-card">
            <span>Open Positions</span>
            <strong>{positions.length}</strong>
          </div>
          <div className="summary-card">
            <span>Unrealized PnL</span>
            <strong className={totalPnl >= 0 ? "positive" : "negative"}>
              {money(totalPnl)}
            </strong>
          </div>
        </section>

        <section className="terminal-grid">
          <div className="left-stack">
            <section className="panel">
              <div className="panel-header">
                <h2>Watchlist</h2>
                <span>Live simulated prices</span>
              </div>

              <div className="watchlist">
                {Object.entries(prices).map(([symbol, price]) => (
                  <div className="ticker-card" key={symbol}>
                    <div>
                      <h3>{symbol}</h3>
                      <p>{money(price)}</p>
                    </div>
                    <button onClick={() => buy(symbol)}>Buy</button>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel chart-panel">
              <div className="panel-header">
                <h2>Equity Curve</h2>
                <span>{equity.length} snapshots</span>
              </div>

              <svg viewBox="0 0 900 260" className="equity-chart">
                <line x1="0" y1="130" x2="900" y2="130" className="midline" />
                <polyline points={chartPoints} />
              </svg>
            </section>

            <section className="panel">
              <div className="panel-header">
                <h2>Positions</h2>
                <span>Mark-to-market</span>
              </div>

              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Qty</th>
                    <th>Avg Price</th>
                    <th>PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p, i) => (
                    <tr key={i}>
                      <td>{p.symbol}</td>
                      <td>{p.qty}</td>
                      <td>{money(p.avg_price)}</td>
                      <td className={p.pnl >= 0 ? "positive" : "negative"}>
                        {money(p.pnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {!positions.length && <p className="empty">No open positions</p>}
            </section>
          </div>

          <aside className="right-stack">
            <section className="panel order-panel">
              <div className="panel-header">
                <h2>Quick Order</h2>
                <span>Market buy</span>
              </div>

              {Object.entries(prices).map(([symbol, price]) => (
                <button
                  className="order-button"
                  key={symbol}
                  onClick={() => buy(symbol)}
                >
                  Buy {symbol}
                  <span>{money(price)}</span>
                </button>
              ))}
            </section>

            <section className="panel timeline-panel">
              <div className="panel-header">
                <h2>Trade Timeline</h2>
                <span>{trades.length} fills</span>
              </div>

              <div className="timeline">
                {trades.slice().reverse().map((t, i) => (
                  <div className="trade-item" key={i}>
                    <span className={`badge ${t.side?.toLowerCase()}`}>
                      {t.side}
                    </span>
                    <div>
                      <strong>{t.symbol}</strong>
                      <p>{t.qty} @ {money(t.price)}</p>
                    </div>
                  </div>
                ))}

                {!trades.length && <p className="empty">No trades yet</p>}
              </div>
            </section>
          </aside>
        </section>
      </main>
    </div>
  );
}