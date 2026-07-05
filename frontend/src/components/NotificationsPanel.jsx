import { useEffect, useState } from "react";

const API = "/api";

const IMPORTANT_TYPES = ["FILLED", "SELL", "ERROR", "REJECTED"];

export default function NotificationsPanel() {
  const [toast, setToast] = useState(null);
  const [lastMessage, setLastMessage] = useState("");

  async function checkActivity() {
    try {
      const data = await fetch(`${API}/activity`).then((r) => r.json());

      if (!Array.isArray(data) || data.length === 0) return;

      const latest = data[0];

      if (
        IMPORTANT_TYPES.includes(latest.type) &&
        latest.message !== lastMessage
      ) {
        setLastMessage(latest.message);
        setToast(latest);

        setTimeout(() => {
          setToast(null);
        }, 4500);
      }
    } catch (err) {
      console.error("NOTIFICATION ERROR:", err);
    }
  }

  useEffect(() => {
    checkActivity();

    const id = setInterval(checkActivity, 3000);

    return () => clearInterval(id);
  }, [lastMessage]);

  if (!toast) return null;

  return (
    <div className={`toast-notification ${toast.type.toLowerCase()}`}>
      <strong>{toast.type}</strong>
      <p>{toast.message}</p>
      <span>{toast.time}</span>
    </div>
  );
}