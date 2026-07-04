import { useEffect, useState } from "react";

const API = "/api";

export default function MarketScannerPanel({ onSelect }) {
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(false);

  const runScan = async () => {
    setLoading(true);

    try {
      const data = await fetch(`${API}/scan?limit=8`).then((r) => r.json());
      setScan(data);
    } catch (err) {
      console.error("SCAN ERROR:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runScan();
    const id = setInterval(runScan, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="panel scanner-panel">
      <div className="panel-header">
        <h2>Kyle AI Scanner</h2>
        <span>{loading ? "Scanning..." : `${scan?.symbols_scanned ?? 0} symbols`}</span>
      </div>

      <button className="order-submit" onClick={runScan}>
        {loading ? "Scanning..." : "Run Scan"}
      </button>

      <div className="scanner-list">
        {scan?.opportunities?.map((item, index) => (
          <div
            className="scanner-row"
            key={item.symbol}
            onClick={() => onSelect(item.symbol)}
          >
            <div className="scanner-rank">{index + 1}</div>

            <div>
              <strong>{item.symbol}</strong>
              <p>{item.recommendation}</p>
            </div>

            <div className="scanner-score">
              <strong>{Number(item.confidence).toFixed(0)}%</strong>
              <span>{item.trade_action}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}