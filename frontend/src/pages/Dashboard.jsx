import { useEffect, useState } from "react";

import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import SummaryCards from "../components/SummaryCards";
import TradingChart from "../components/TradingChart";
import Watchlist from "../components/Watchlist";
import MarketScannerPanel from "../components/MarketScannerPanel";
import PortfolioHealthPanel from "../components/PortfolioHealthPanel";
import PortfolioCoachPanel from "../components/PortfolioCoachPanel";
import TradeAdvicePanel from "../components/TradeAdvicePanel";
import AIAssistantPanel from "../components/AIAssistantPanel";
import OrderTicket from "../components/OrderTicket";
import BacktesterPanel from "../components/BacktesterPanel";
import PositionsTable from "../components/PositionsTable";
import TradeTimeline from "../components/TradeTimeline";
import DailyPlanPanel from "../components/DailyPlanPanel";

import "./dashboard.css";

const API = "/api";

export default function Dashboard() {
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [trades, setTrades] = useState([]);
  const [prices, setPrices] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState("AAPL");

  async function loadDashboard() {
    try {
      const [accountData, positionsData, tradesData, pricesData] =
        await Promise.all([
          fetch(`${API}/account`).then((r) => r.json()),
          fetch(`${API}/positions`).then((r) => r.json()),
          fetch(`${API}/trades`).then((r) => r.json()),
          fetch(`${API}/prices`).then((r) => r.json()),
        ]);

      setAccount(accountData);
      setPositions(positionsData);
      setTrades(tradesData);
      setPrices(pricesData);
    } catch (err) {
      console.error(err);
    }
  }

  useEffect(() => {
    loadDashboard();
    const timer = setInterval(loadDashboard, 2500);
    return () => clearInterval(timer);
  }, []);

  async function buy(symbol) {
    try {
      await fetch(`${API}/buy/${symbol}`, { method: "POST" });
      loadDashboard();
    } catch (err) {
      console.error(err);
    }
  }

  function handleSelectSymbol(symbol) {
    setSelectedSymbol(symbol);
  }

  const totalPnl = positions.reduce(
    (sum, p) => sum + Number(p.pnl || 0),
    0
  );

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

        <DailyPlanPanel onSelect={handleSelectSymbol} />

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

            <PortfolioHealthPanel />

            <PortfolioCoachPanel onSelect={handleSelectSymbol} />

            <TradeAdvicePanel symbol={selectedSymbol} />

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