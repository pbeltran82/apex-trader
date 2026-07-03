const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

export default function PositionsTable({ positions }) {
  return (
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
  );
}