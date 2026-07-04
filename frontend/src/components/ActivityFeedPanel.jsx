import { useEffect, useState } from "react";

const API = "/api";

const ICONS = {
  SYSTEM: "⚙️",
  QUEUE: "📥",
  CHECKING: "🟡",
  EXECUTING: "🟠",
  FILLED: "🟢",
  ACTIVE: "🚀",
  COMPLETED: "✅",
  REJECTED: "🔴",
  ERROR: "❌",
  WAITING: "⏳",
};

export default function ActivityFeedPanel() {
  const [events, setEvents] = useState([]);

  async function loadActivity() {
    try {
      const data = await fetch(`${API}/activity`).then((r) => r.json());
      setEvents(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    }
  }

  useEffect(() => {
    loadActivity();

    const id = setInterval(loadActivity, 3000);

    return () => clearInterval(id);
  }, []);

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Live Activity</h2>
        <span>{events.length} events</span>
      </div>

      {events.length === 0 ? (
        <p className="empty">Kyle is waiting for market activity...</p>
      ) : (
        <div className="activity-feed">
          {events.map((event, index) => (
            <div className="activity-row" key={index}>
              <div className="activity-icon">
                {ICONS[event.type] || "📌"}
              </div>

              <div className="activity-content">
                <div className="activity-message">
                  {event.message}
                </div>

                <div className="activity-time">
                  {event.time}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}