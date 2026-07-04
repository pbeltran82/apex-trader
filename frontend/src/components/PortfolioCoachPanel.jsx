import { useEffect, useState } from "react";

const API = "/api";

export default function PortfolioCoachPanel({ onSelect }) {
  const [coach, setCoach] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadCoach = async () => {
    setLoading(true);

    try {
      const data = await fetch(`${API}/portfolio-coach`).then((r) => r.json());
      setCoach(data);
    } catch (err) {
      console.error("PORTFOLIO COACH ERROR:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCoach();
    const id = setInterval(loadCoach, 30000);
    return () => clearInterval(id);
  }, []);

  if (!coach) return null;

  return (
    <section className="panel portfolio-coach-panel">
      <div className="panel-header">
        <h2>Kyle AI Coach</h2>
        <span>{loading ? "Thinking..." : "Live"}</span>
      </div>

      <div className="coach-messages">
        {coach.coach_messages?.map((msg, i) => (
          <p key={i}>{msg}</p>
        ))}
      </div>

      <div className="coach-ideas">
        <h4>Top Ideas</h4>

        {coach.ideas?.map((idea) => (
          <button
            key={idea.symbol}
            className="coach-idea"
            onClick={() => onSelect(idea.symbol)}
          >
            <span>{idea.symbol}</span>
            <strong>{Number(idea.confidence).toFixed(0)}%</strong>
            <small>{idea.action}</small>
          </button>
        ))}
      </div>
    </section>
  );
}