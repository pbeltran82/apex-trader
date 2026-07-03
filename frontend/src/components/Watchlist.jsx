const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

export default function Watchlist({ prices, selectedSymbol, onSelect, onBuy }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Watchlist</h2>
        <span>Click symbol to chart</span>
      </div>

      <div className="watchlist-list">
        {Object.entries(prices).map(([symbol, price]) => (
          <div
            className={
              selectedSymbol === symbol
                ? "watchlist-row selected"
                : "watchlist-row"
            }
            key={symbol}
            onClick={() => onSelect(symbol)}
          >
            <div>
              <strong>{symbol}</strong>
              <p>{money(price)}</p>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                onBuy(symbol);
              }}
            >
              Buy
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}