import { useEffect, useState } from "react";

const API = "/api";

export default function DailyPlanPanel({ onSelect }) {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadPlan = async () => {
    setLoading(true);

    try {
      const data = await fetch(`${API}/daily-plan`).then((r) => r.json());
      setPlan(data);
    } catch (err) {
      console.error("DAILY PLAN ERROR:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlan();
    const id = setInterval(loadPlan, 30000);
    return () => clearInterval(id);
  }, []);

  if (!plan) return null;

  return (
    <section className="panel daily-plan-panel">
      <div className="panel-header">
        <h2>Today's Game Plan</h2>
        <span>{loading ? "Planning..." : plan.market_bias}</span>
      </div>

      <div className="daily-plan-summary">
        <div>
          <span>Capital</span>
          <strong>${plan.recommended_capital}</strong>
        </div>

        <div>
          <span>Risk</span>
          <strong>{plan.portfolio_risk}</strong>
        </div>

        <div>
          <span>Max Trades</span>
          <strong>{plan.max_trades}</strong>
        </div>
      </div>

      <div className="daily-plan-picks">
        {plan.top_picks?.map((pick, index) => (
          <button
            className="daily-pick"
            key={pick.symbol}
            onClick={() => onSelect(pick.symbol)}
          >
            <span>{index + 1}</span>
            <strong>{pick.symbol}</strong>
            <em>{Number(pick.confidence).toFixed(0)}%</em>
            <small>{pick.shares} sh</small>
          </button>
        ))}
      </div>

      <p className="daily-plan-text">{plan.summary}</p>
    </section>
  );
}