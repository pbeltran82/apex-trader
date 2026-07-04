import { useEffect, useState } from "react";

const API = "/api";

export default function PortfolioHealthPanel() {
  const [portfolio, setPortfolio] = useState(null);

  const load = async () => {
    try {
      const data = await fetch(`${API}/portfolio-analysis`).then((r) =>
        r.json()
      );
      setPortfolio(data);
    } catch (err) {
      console.error("PORTFOLIO AI ERROR:", err);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  if (!portfolio) return null;

  return (
    <section className="panel portfolio-health-panel">
      <div className="panel-header">
        <h2>Portfolio Health</h2>
        <span>Grade {portfolio.portfolio_grade}</span>
      </div>

      <div className="portfolio-health-grid">
        <div>
          <span>Value</span>
          <strong>${portfolio.portfolio_value}</strong>
        </div>

        <div>
          <span>Cash</span>
          <strong>{portfolio.cash_pct}%</strong>
        </div>

        <div>
          <span>Diversification</span>
          <strong>{portfolio.diversification_score}%</strong>
        </div>

        <div>
          <span>Risk</span>
          <strong>{portfolio.risk_level}</strong>
        </div>
      </div>

      <div className="portfolio-recommendations">
        <h4>Kyle AI Notes</h4>
        <ul>
          {portfolio.recommendations?.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}