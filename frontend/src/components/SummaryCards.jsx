const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

export default function SummaryCards({ account, openPositions, totalPnl }) {
  return (
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
        <strong>{openPositions}</strong>
      </div>

      <div className="summary-card">
        <span>Unrealized PnL</span>
        <strong className={totalPnl >= 0 ? "positive" : "negative"}>
          {money(totalPnl)}
        </strong>
      </div>
    </section>
  );
}