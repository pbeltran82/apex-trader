import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
} from "lightweight-charts";

const API = "/api";

const TIMEFRAMES = [
  { label: "1m", seconds: 60 },
  { label: "5m", seconds: 300 },
  { label: "15m", seconds: 900 },
  { label: "1H", seconds: 3600 },
];

const money = (n) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(n ?? 0));

const fmt = (n) => Number(n ?? 0).toFixed(2);

function aggregateCandles(candles, bucketSeconds) {
  const clean = candles
    .map((c) => ({
      time: Number(c.time),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
      volume: Number(c.volume ?? 0),
    }))
    .filter((c) => Number.isFinite(c.time))
    .sort((a, b) => a.time - b.time);

  if (bucketSeconds === 60) return clean;

  const groups = new Map();

  for (const c of clean) {
    const bucket = Math.floor(c.time / bucketSeconds) * bucketSeconds;

    if (!groups.has(bucket)) {
      groups.set(bucket, { ...c, time: bucket });
    } else {
      const g = groups.get(bucket);
      g.high = Math.max(g.high, c.high);
      g.low = Math.min(g.low, c.low);
      g.close = c.close;
      g.volume += c.volume;
    }
  }

  return Array.from(groups.values()).sort((a, b) => a.time - b.time);
}

export default function TradingChart({
  symbol = "AAPL",
  symbols = ["AAPL", "TSLA", "NVDA"],
  prices = {},
  onSymbolChange,
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleRef = useRef(null);
  const volumeRef = useRef(null);

  const [timeframe, setTimeframe] = useState(TIMEFRAMES[0]);
  const [ohlc, setOhlc] = useState(null);
  const [lastPrice, setLastPrice] = useState(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 640,
      layout: {
        background: { color: "#07111f" },
        textColor: "#cbd5e1",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      rightPriceScale: {
        borderColor: "rgba(148,163,184,0.18)",
      },
      timeScale: {
        borderColor: "rgba(148,163,184,0.18)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1,
      },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
    });

    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "",
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    chart.subscribeCrosshairMove((param) => {
      if (!param?.time || !param.seriesData) return;
      const data = param.seriesData.get(candles);
      if (data) setOhlc(data);
    });

    chartRef.current = chart;
    candleRef.current = candles;
    volumeRef.current = volume;

    const resize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    };

    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    const loadCandles = async () => {
      if (!candleRef.current || !volumeRef.current) return;

      const raw = await fetch(`${API}/candles/${symbol}`).then((r) => r.json());

      const unique = Array.from(
        new Map(raw.map((c) => [Number(c.time), c])).values()
      );

      const aggregated = aggregateCandles(unique, timeframe.seconds);

      const candleData = aggregated.map((c) => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));

      const volumeData = aggregated.map((c) => ({
        time: c.time,
        value: c.volume,
        color:
          c.close >= c.open
            ? "rgba(34,197,94,0.45)"
            : "rgba(239,68,68,0.45)",
      }));

      candleRef.current.setData(candleData);
      volumeRef.current.setData(volumeData);

      const latest = candleData[candleData.length - 1];
      if (latest) {
        setLastPrice(latest.close);
        setOhlc(latest);
      }

      chartRef.current?.timeScale().fitContent();
    };

    loadCandles();
    const id = setInterval(loadCandles, 2500);
    return () => clearInterval(id);
  }, [symbol, timeframe]);

  return (
    <section className="panel chart-panel-main">
      <div className="chart-topbar">
        <div className="symbol-tabs">
          {symbols.map((s) => (
            <button
              key={s}
              className={symbol === s ? "chart-tab active" : "chart-tab"}
              onClick={() => onSymbolChange(s)}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="timeframe-tabs">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.label}
              className={
                timeframe.label === tf.label ? "chart-tab active" : "chart-tab"
              }
              onClick={() => setTimeframe(tf)}
            >
              {tf.label}
            </button>
          ))}
        </div>

        <div className="live-price">
          <span className="pulse" />
          {money(prices[symbol] ?? lastPrice)}
        </div>
      </div>

      <div className="panel-header chart-title-row">
        <div>
          <h2>{symbol} Candlestick Chart</h2>
          <span>Backend OHLC · {timeframe.label} candles</span>
        </div>

        {ohlc && (
          <div className="ohlc-panel">
            <span>O {fmt(ohlc.open)}</span>
            <span>H {fmt(ohlc.high)}</span>
            <span>L {fmt(ohlc.low)}</span>
            <span>C {fmt(ohlc.close)}</span>
          </div>
        )}
      </div>

      <div ref={containerRef} className="trading-chart" />
    </section>
  );
}