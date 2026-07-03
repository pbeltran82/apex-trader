export default function Header({ selectedSymbol }) {
  return (
    <header className="terminal-header">
      <div>
        <h1>
          Kyle Trader <span>Paper Trading</span>
        </h1>
        <p>
          TradingView-style chart · selected symbol:{" "}
          <strong>{selectedSymbol}</strong>
        </p>
      </div>

      <div className="market-pill">
        <span className="pulse" />
        Market: Simulated
      </div>
    </header>
  );
}