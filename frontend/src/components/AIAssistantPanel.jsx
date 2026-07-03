import { useEffect, useState } from "react";

const API = "/api";

export default function AIAssistantPanel({ symbol }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadAnalysis = async () => {
    if (!symbol) return;

    setLoading(true);

    try {
      const data = await fetch(`${API}/ai/analyze/${symbol}`).then((r) =>
        r.json()
      );

      setAnalysis(data);
    } catch (err) {
      console.error("AI ANALYSIS ERROR:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnalysis();
  }, [symbol]);

  if (loading || !analysis) {
    return (
      <section className="panel ai-card">
        <div className="panel-header">
          <h2>AI Trading Assistant</h2>
          <span>{symbol}</span>
        </div>
        <p className="empty">Analyzing market...</p>
      </section>
    );
  }

  if (analysis.error) {
    return (
      <section className="panel ai-card">
        <div className="panel-header">
          <h2>AI Trading Assistant</h2>
          <span>{symbol}</span>
        </div>
        <p className="negative">{analysis.error}</p>
      </section>
    );
  }

  return (
    <section className="panel ai-card">
      <div className="panel-header">
        <h2>AI Trading Assistant</h2>
        <span>{analysis.symbol}</span>
      </div>

      <div className="ai-score">
        <div className="score-circle">{Number(analysis.confidence).toFixed(0)}%</div>

        <div>
          <div
            className={
              analysis.recommendation.includes("BUY")
                ? "recommendation positive"
                : analysis.recommendation.includes("AVOID")
                ? "recommendation negative"
                : "recommendation"
            }
          >
            {analysis.recommendation}
          </div>

          <div className="ai-symbol">{analysis.symbol}</div>
        </div>
      </div>

      <div className="metrics">
        <div>
          <span>Trend</span>
          <strong>{analysis.trend}</strong>
        </div>

        <div>
          <span>Momentum</span>
          <strong>{analysis.momentum}</strong>
        </div>

        <div>
          <span>MACD</span>
          <strong>{analysis.macd_signal}</strong>
        </div>

        <div>
          <span>Volume</span>
          <strong>{analysis.volume_signal}</strong>
        </div>

        <div>
          <span>RSI</span>
          <strong>{analysis.rsi}</strong>
        </div>

        <div>
          <span>Risk</span>
          <strong>{analysis.risk_score}%</strong>
        </div>
      </div>

      <div className="support-box">
        <div>
          <small>Support</small>
          <h4>${analysis.support}</h4>
        </div>

        <div>
          <small>Resistance</small>
          <h4>${analysis.resistance}</h4>
        </div>
      </div>

      <div className="reasoning">
        <h4>AI Reasoning</h4>

        <ul>
          {analysis.reasoning?.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="disclaimer">{analysis.disclaimer}</div>
    </section>
  );
}