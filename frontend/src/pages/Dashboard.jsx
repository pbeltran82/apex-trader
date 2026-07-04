import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import SummaryCards from "../components/SummaryCards";
import TradingChart from "../components/TradingChart";
import Watchlist from "../components/Watchlist";
import MarketScannerPanel from "../components/MarketScannerPanel";
import AIAssistantPanel from "../components/AIAssistantPanel";
import OrderTicket from "../components/OrderTicket";
import BacktesterPanel from "../components/BacktesterPanel";
import PositionsTable from "../components/PositionsTable";
import TradeTimeline from "../components/TradeTimeline";
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
      const [accountRes, positionsRes, tradesRes, pricesRes] =
        await Promise.all([
          fetch(`${API}/account`).then((r) => r.json()),
          fetch(`${API}/positions`).then((r) => r.json()),
          fetch(`${API}/trades`).then((r) => r.json()),
          fetch(`${API}/prices`).then((r) => r.json()),
        ]);

      setAccount(accountRes);
      setPositions(positionsRes);
      setTrades(tradesRes);
      setPrices(pricesRes);
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

  const handleSelectSymbol = (symbol) => {
    setSelectedSymbol(symbol);
  };

  const totalPnl = positions.reduce((sum, p) => {
    return sum + Number(p.pnl ?? 0);
  }, 0);

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
              onSymbolChange={handleSelectSymbol}
            />

            <PositionsTable positions={positions} />
          </section>

          <aside className="right-rail">
            <Watchlist
              prices={prices}
              selectedSymbol={selectedSymbol}
              onSelect={handleSelectSymbol}
              onBuy={buy}
            />

            <MarketScannerPanel onSelect={handleSelectSymbol} />

            <AIAssistantPanel symbol={selectedSymbol} />

            <OrderTicket
              prices={prices}
              selectedSymbol={selectedSymbol}
              onSymbolChange={handleSelectSymbol}
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