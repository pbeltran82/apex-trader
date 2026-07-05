import { useEffect, useState } from "react";

const API = "/api";

export default function EquityCurvePanel() {
  const [points, setPoints] = useState([]);

  const load = async () => {
    try {
      const data = await fetch(`${API}/equity-curve`).then((r) => r.json());
      setPoints(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("EQUITY CURVE ERROR:", err);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const values = points.map((p) => Number(p.equity || 0));
  const min = Math.min(...values, 10000);
  const max = Math.max(...values, 10000);
  const range = max - min || 1;

  const path = values
    .map((value, index) => {
      const x = values.length <= 1 ? 0 : (index / (values.length - 1)) * 100;
      const y = 100 - ((value - min) / range) * 100;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  const latest = values[values.length - 1] ?? 10000;

  return (
    <section className="panel equity-curve-panel">
      <div className="panel-header">
        <h2>Equity Curve</h2>
        <span>${latest.toFixed(2)}</span>
      </div>

      <div className="equity-chart">
        {values.length > 1 ? (
          <svg viewBox="0 0 100 100" preserveAspectRatio="none">
            <path d={path} />
          </svg>
        ) : (
          <p className="empty">Waiting for equity history...</p>
        )}
      </div>

      <div className="equity-range">
        <span>Low ${min.toFixed(2)}</span>
        <span>High ${max.toFixed(2)}</span>
      </div>
    </section>
  );
}