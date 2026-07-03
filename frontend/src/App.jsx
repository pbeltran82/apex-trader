import { useEffect, useState } from "react";
import { getAccount, getPositions, getTrades } from "./services/api";

function App() {
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [acc, pos, trd] = await Promise.all([
        getAccount(),
        getPositions(),
        getTrades(),
      ]);

      setAccount(acc.data);
      setPositions(pos.data);
      setTrades(trd.data);
    } catch (err) {
      console.error("API error:", err);
    }
  };

  return (
    <div style={{ padding: 20, fontFamily: "sans-serif" }}>
      <h1>Apex Trader Dashboard</h1>

      <h2>Account</h2>
      {account && (
        <pre>{JSON.stringify(account, null, 2)}</pre>
      )}

      <h2>Positions</h2>
      <pre>{JSON.stringify(positions, null, 2)}</pre>

      <h2>Trades</h2>
      <pre>{JSON.stringify(trades, null, 2)}</pre>
    </div>
  );
}

export default App;