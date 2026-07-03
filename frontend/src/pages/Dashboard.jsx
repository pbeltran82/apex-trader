import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import SummaryCards from "../components/SummaryCards";
import TradingChart from "../components/TradingChart";
import Watchlist from "../components/Watchlist";
import OrderTicket from "../components/OrderTicket";
import PositionsTable from "../components/PositionsTable";
import TradeTimeline from "../components/TradeTimeline";
import BacktesterPanel from "../components/BacktesterPanel";
import AIAssistantPanel from "../components/AIAssistantPanel";
import "./dashboard.css";

const API = "/api";

export default function Dashboard() {
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [prices, setPrices] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState("AAPL");

  const load = async () => {
    try {
      const [a, p, t, pr] = await Promise.all([
        fetch(`${API}/account`).then((r) => r.json()),
        fetch(`${API}/positions`).then((r) => r.json()),
        fetch(`${API}/trades`).then((r) => r.json()),
        fetch(`${API}/prices`).then((r) => r.json()),
      ]);

      setAccount(a);
      setPositions(p);
      setTrades(t);
      setPrices(pr);
    } catch (err) {
      console.error("API ERROR:", err);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 2500);
    return () => clearInterval(id);
  }, []);

  const buy = async (symbol) => {
    await fetch(`${API}/buy/${symbol}`, { method: "POST" });
    await load();
  };

  const totalPnl = positions.reduce((sum, p) => sum + Number(p.pnl ?? 0), 0);

  return (
    <div className="terminal-shell">
      <Sidebar />

      <main className="terminal-main">
        <Header selectedSymbol={selectedSymbol} />

        <SummaryCards
          account={account}
          openPositions={positions.length}
          totalPnl={totalPnl}
        />

        <section className="terminal-workspace">
          <section className="chart-column">
            <TradingChart
              symbol={selectedSymbol}
              symbols={Object.keys(prices)}
              prices={prices}
              onSymbolChange={setSelectedSymbol}
            />

            <PositionsTable positions={positions} />
          </section>

         <aside className="right-rail">
  <Watchlist
    prices={prices}
    selectedSymbol={selectedSymbol}
    onSelect={setSelectedSymbol}
    onBuy={buy}
  />

  <AIAssistantPanel symbol={selectedSymbol} />

  <OrderTicket
    prices={prices}
    selectedSymbol={selectedSymbol}
    onSymbolChange={setSelectedSymbol}
    onBuy={buy}
  />

  <BacktesterPanel selectedSymbol={selectedSymbol} />

  <TradeTimeline trades={trades} />
</aside>
        </section>
      </main>
    </div>
  );
}