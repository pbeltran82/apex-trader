const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

export default function TradeTimeline({ trades }) {
  return (
    <section className="panel timeline-panel">
      <div className="panel-header">
        <h2>Trade Timeline</h2>
        <span>{trades.length} fills</span>
      </div>

      <div className="timeline">
        {trades.slice().reverse().map((t, i) => (
          <div className="trade-item" key={i}>
            <span className={`badge ${t.side?.toLowerCase()}`}>{t.side}</span>
            <div>
              <strong>{t.symbol}</strong>
              <p>
                {t.qty} @ {money(t.price)}
              </p>
            </div>
          </div>
        ))}

        {!trades.length && <p className="empty">No trades yet</p>}
      </div>
    </section>
  );
}