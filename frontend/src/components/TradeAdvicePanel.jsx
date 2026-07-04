import { useEffect, useState } from "react";

const API = "/api";

export default function TradeAdvicePanel({ symbol }) {
  const [advice, setAdvice] = useState(null);

  const loadAdvice = async () => {
    try {
      const data = await fetch(`${API}/position-advice/${symbol}`).then((r) =>
        r.json()
      );
      setAdvice(data);
    } catch (err) {
      console.error("TRADE ADVICE ERROR:", err);
    }
  };

  useEffect(() => {
    if (!symbol) return;

    loadAdvice();
    const id = setInterval(loadAdvice, 5000);

    return () => clearInterval(id);
  }, [symbol]);

  if (!advice) return null;

  return (
    <section className="panel trade-advice-panel">
      <div className="panel-header">
        <h2>Kyle Trade Card</h2>
        <span>{advice.symbol}</span>
      </div>

      <div className={`trade-verdict ${advice.approved ? "approved" : "rejected"}`}>
        <strong>{advice.action}</strong>
        <p>{advice.approved ? "Approved setup" : "Rejected setup"}</p>
      </div>

      {advice.approved ? (
        <div className="trade-advice-grid">
          <div>
            <span>Allocation</span>
            <strong>{advice.recommended_allocation_pct}%</strong>
          </div>

          <div>
            <span>Shares</span>
            <strong>{advice.recommended_shares}</strong>
          </div>

          <div>
            <span>Cost</span>
            <strong>${advice.recommended_dollars}</strong>
          </div>

          <div>
            <span>Cash After</span>
            <strong>${advice.cash_after_trade}</strong>
          </div>

          <div>
            <span>Sector</span>
            <strong>{advice.sector}</strong>
          </div>

          <div>
            <span>Sector After</span>
            <strong>{advice.sector_exposure_after_trade}%</strong>
          </div>
        </div>
      ) : (
        <div className="trade-reject-box">
          <strong>Reason</strong>
          <p>{advice.reason}</p>
        </div>
      )}

      <div className="trade-reason">
        <strong>Kyle Reasoning</strong>
        <p>{advice.reason}</p>
      </div>

      {advice.warnings?.length > 0 && (
        <div className="trade-warnings">
          <strong>Warnings</strong>
          <ul>
            {advice.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}