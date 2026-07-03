import { useState, useEffect } from "react";

const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

export default function OrderTicket({
  prices,
  selectedSymbol,
  onSymbolChange,
  onBuy,
}) {
  const symbols = Object.keys(prices);
  const [qty, setQty] = useState(1);

  useEffect(() => {
    if (!selectedSymbol && symbols.length > 0) {
      onSymbolChange(symbols[0]);
    }
  }, [symbols, selectedSymbol, onSymbolChange]);

  const price = prices[selectedSymbol] ?? 0;
  const estimatedCost = price * Number(qty || 0);

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Order Ticket</h2>
        <span>Market order</span>
      </div>

      <div className="order-form">
        <label>
          Symbol
          <select
            value={selectedSymbol}
            onChange={(e) => onSymbolChange(e.target.value)}
          >
            {symbols.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>

        <label>
          Quantity
          <input
            type="number"
            min="1"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
          />
        </label>

        <div className="estimate">
          <span>Estimated Cost</span>
          <strong>{money(estimatedCost)}</strong>
        </div>

        <button
          className="order-submit"
          onClick={async () => {
            for (let i = 0; i < Number(qty); i++) {
              await onBuy(selectedSymbol);
            }
          }}
        >
          Buy {selectedSymbol}
        </button>
      </div>
    </section>
  );
}