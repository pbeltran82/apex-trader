export default function SummaryCards({ portfolio }) {
  const cash = portfolio?.cash ?? 0;
  const equity = portfolio?.equity ?? 0;
  const openPositions = portfolio?.open_positions ?? 0;
  const totalPnl = portfolio?.unrealized_pnl ?? 0;
  const exposurePct = portfolio?.exposure_pct ?? 0;

  const money = (value) =>
    Number(value || 0).toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
    });

  return (
    <section className="summary-grid">
      <div className="summary-card">
        <span>Cash</span>
        <strong>{money(cash)}</strong>
      </div>

      <div className="summary-card">
        <span>Equity</span>
        <strong>{money(equity)}</strong>
      </div>

      <div className="summary-card">
        <span>Open Positions</span>
        <strong>{openPositions}</strong>
      </div>

      <div className="summary-card">
        <span>Unrealized P/L</span>
        <strong className={totalPnl >= 0 ? "positive" : "negative"}>
          {money(totalPnl)}
        </strong>
      </div>

      <div className="summary-card">
        <span>Exposure</span>
        <strong>{Number(exposurePct).toFixed(2)}%</strong>
      </div>
    </section>
  );
}