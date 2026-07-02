---
name: Trade attribution schema
description: TradeAttribution dataclass design — shared contract between live engine and backtest, serialization gotchas, and why strategies always run on risk-blocked bars.
---

## Rule
`TradeAttribution` is the single explainability contract for both live (`evaluate_attributed`) and backtest (`TradeEvent.attribution`). The schema must stay identical across both modes.

**Why:** The architectural invariant is that backtest == live behavior. Attribution is proof of that — if the schema diverged it would mean the execution paths diverged.

## Schema
```json
{
  "decided_by": "risk_block | strategy | snapshot_error",
  "risk": {
    "blocked": true,
    "violations": [{"reason": "..."}]
  },
  "strategy": {
    "all": [{"name": "...", "action": "...", "confidence": 0.0, "reason": "...", "metadata": {}}],
    "selected": {"name": "...", "action": "...", "confidence": 0.0, ...},
    "combiner_rule": "highest_confidence_non_hold_wins"
  }
}
```

## How to apply
- `evaluate_attributed()` always runs strategies even when risk blocks — attribution must show what strategies saw regardless of outcome.
- Backtest loop: build `TradeAttribution` BEFORE the `if violations: continue` guard; attach via `attribution=attribution.to_dict()` on `TradeEvent`.
- `TradeEvent` serialization is inline in `BacktestResult.to_dict()` — the `attribution` field must be explicitly added there; it won't appear automatically from the dataclass.
- `TradeAttribution` is lighter than `PipelineTrace` — no snapshot dump, pure decision provenance. Use `PipelineTrace` for full debug; `TradeAttribution` for per-trade explainability.
