import "./dashboard.css";
import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import SummaryCards from "../components/SummaryCards";
import DailyPlanPanel from "../components/DailyPlanPanel";
import TradingChart from "../components/TradingChart";
import Watchlist from "../components/Watchlist";
import MarketScannerPanel from "../components/MarketScannerPanel";
import PortfolioHealthPanel from "../components/PortfolioHealthPanel";
import ExecutionQueuePanel from "../components/ExecutionQueuePanel";
import ActivityFeedPanel from "../components/ActivityFeedPanel";
import PortfolioCoachPanel from "../components/PortfolioCoachPanel";
import TradeAdvicePanel from "../components/TradeAdvicePanel";
import AIAssistantPanel from "../components/AIAssistantPanel";
import OrderTicket from "../components/OrderTicket";
import BacktesterPanel from "../components/BacktesterPanel";
import PositionsTable from "../components/PositionsTable";
import TradeTimeline from "../components/TradeTimeline";
import TradeHistoryPanel from "../components/TradeHistoryPanel";
import PerformancePanel from "../components/PerformancePanel";
import AutoExitPanel from "../components/AutoExitPanel";
import NotificationsPanel from "../components/NotificationsPanel";
import EquityCurvePanel from "../components/EquityCurvePanel";



const API = "/api";

export default function Dashboard() {
  const [portfolioLive, setPortfolioLive] = useState(null);
  const [trades, setTrades] = useState([]);
  const [prices, setPrices] = useState({});
  const [selectedSymbol, setSelectedSymbol] = useState("AAPL");

  async function loadDashboard() {
    try {
      const [portfolioData, tradesData, pricesData] = await Promise.all([
        fetch(`${API}/portfolio-live`).then((r) => r.json()),
        fetch(`${API}/trades`).then((r) => r.json()),
        fetch(`${API}/prices`).then((r) => r.json()),
      ]);

      setPortfolioLive(portfolioData);
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
      await fetch(`${API}/buy/${symbol}`, {
        method: "POST",
      });

      loadDashboard();
    } catch (err) {
      console.error(err);
    }
  }

  function handleSelectSymbol(symbol) {
    setSelectedSymbol(symbol);
  }

  return (
    <div className="terminal-shell">
      <Sidebar />

      <main className="terminal-main">
        <Header selectedSymbol={selectedSymbol} />

        <SummaryCards portfolio={portfolioLive} />

        <DailyPlanPanel onSelect={handleSelectSymbol} />

        <section className="terminal-workspace">
          <section className="chart-column">
            <TradingChart
              symbol={selectedSymbol}
              symbols={Object.keys(prices)}
              prices={prices}
              onSymbolChange={handleSelectSymbol}
            />

            <PositionsTable positions={portfolioLive?.positions || []} />

          <PerformancePanel />

          <EquityCurvePanel />

          <AutoExitPanel />

          </section>

          <aside className="right-rail">
            <Watchlist
              prices={prices}
              selectedSymbol={selectedSymbol}
              onSelect={handleSelectSymbol}
              onBuy={buy}
            />

            <NotificationsPanel />

            <MarketScannerPanel onSelect={handleSelectSymbol} />

            <PortfolioHealthPanel />

            <ExecutionQueuePanel />

            <ActivityFeedPanel />

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

            <TradeHistoryPanel />

            <TradeTimeline trades={trades} />
          </aside>
        </section>
      </main>
    </div>
  );
}