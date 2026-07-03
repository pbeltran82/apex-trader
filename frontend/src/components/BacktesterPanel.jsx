import { useEffect, useState } from "react";

const API = "/api";

const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

export default function BacktesterPanel({ selectedSymbol }) {
  const [strategies, setStrategies] = useState([]);
  const [strategy, setStrategy] = useState("ema");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/backtest-strategies`)
      .then((r) => r.json())
      .then(setStrategies)
      .catch((err) => console.error("STRATEGY LOAD ERROR:", err));
  }, []);

  const runBacktest = async () => {
    setLoading(true);

    try {
      const data = await fetch(
        `${API}/backtest/${selectedSymbol}?strategy=${strategy}`
      ).then((r) => r.json());

      setResult(data);
    } catch (err) {
      console.error("BACKTEST ERROR:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>AI Backtester</h2>
        <span>{selectedSymbol}</span>
      </div>

      <div className="backtester-form">
        <label>
          Strategy
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>

        <button className="order-submit" onClick={runBacktest}>
          {loading ? "Running..." : "Run Backtest"}
        </button>
      </div>

      {result && !result.error && (
        <>
          <div className="backtest-results">
            <div>
              <span>Strategy</span>
              <strong>{result.strategy}</strong>
            </div>

            <div>
              <span>Net PnL</span>
              <strong className={result.total_pnl >= 0 ? "positive" : "negative"}>
                {money(result.total_pnl)}
              </strong>
            </div>

            <div>
              <span>Total Return</span>
              <strong className={result.total_return >= 0 ? "positive" : "negative"}>
                {result.total_return}%
              </strong>
            </div>

            <div>
              <span>Win Rate</span>
              <strong>{result.win_rate}%</strong>
            </div>

            <div>
              <span>Trades</span>
              <strong>{result.trades_count}</strong>
            </div>

            <div>
              <span>Profit Factor</span>
              <strong>{result.profit_factor}</strong>
            </div>

            <div>
              <span>Sharpe</span>
              <strong>{result.sharpe}</strong>
            </div>

            <div>
              <span>Max Drawdown</span>
              <strong className="negative">{money(result.max_drawdown)}</strong>
            </div>
          </div>

          <div className="ai-summary">
            <h3>AI Summary</h3>
            <p>{result.ai_summary?.summary}</p>

            <div className="ai-verdict">
              <span>Verdict</span>
              <strong
                className={
                  result.ai_summary?.verdict === "Bullish"
                    ? "positive"
                    : "negative"
                }
              >
                {result.ai_summary?.verdict}
              </strong>
            </div>

            <div className="ai-verdict">
              <span>Confidence</span>
              <strong>{result.ai_summary?.confidence}%</strong>
            </div>

            <ul>
              {result.ai_summary?.recommendations?.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </div>
        </>
      )}

      {result?.error && <p className="negative">{result.error}</p>}
    </section>
  );
}