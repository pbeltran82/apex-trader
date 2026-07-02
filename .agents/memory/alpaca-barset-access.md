---
name: Alpaca BarSet access pattern
description: How to correctly extract bars from the BarSet object returned by get_stock_bars()
---

## Rule

Never use `symbol in bars_data` or `bars_data[symbol]` directly on the BarSet.
Always use: `dict(bars_data).get('data', {}).get(symbol, [])`

## Why

`dict(BarSet)` returns `{'data': {'TSLA': [bars...]}}` — the symbol is nested one level under `'data'`, not at the top level.
`symbol in bars_data` silently returns False because the top-level key is `'data'`, not the symbol.
`bars_data[symbol]` raises KeyError for the same reason.

## How to apply

Everywhere `get_stock_bars()` is called — both live (SnapshotBuilder) and backtest (BacktestEngine):
```python
bars_data = client.get_stock_bars(req)
bars = list(dict(bars_data).get('data', {}).get(symbol, []))
```
