---
name: Alpaca data feed tiers and free plan constraints
description: Which Alpaca data feeds work for what data types on the free plan
---

## Rules

| Use case | Feed | Works on free plan? |
|---|---|---|
| Live latest trade (real-time) | `DataFeed.IEX` | Yes |
| Recent daily bars (last 30 days) | `DataFeed.IEX` | No — IEX doesn't serve historical daily bars |
| Recent daily bars (last 30 days) | default (SIP) | No — "subscription does not permit querying recent SIP data" |
| Historical daily bars (2024 and older) | default (SIP, no feed param) | Yes — works fine |

## Why

Alpaca free plan restricts "recent SIP data" (real-time consolidated feed) but allows historical SIP data.
IEX feed only serves live quotes — it has no historical daily bar data at all.

## How to apply

- `StockLatestTradeRequest`: always use `feed=DataFeed.IEX` for live price
- `StockBarsRequest` for live engine (recent window): use `feed=DataFeed.IEX` — will return 0 bars gracefully; momentum stays at null/low confidence
- `StockBarsRequest` for backtest (historical data): omit feed param (uses SIP default) — returns full history
