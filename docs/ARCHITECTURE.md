# Kyle Architecture

## Philosophy

Kyle is organized into independent layers.

Each layer has one responsibility.

No layer should bypass another.

---

Executive Layer

Executive Dashboard

Operations Dashboard

Mission Control

Readiness Report

↓

Governance Layer

Enterprise Risk

Health Monitor

Validation

Burn-In

↓

Decision Layer

Scanner

Decision Engine

Market Regime

Sector Rotation

Capital Allocation

↓

Execution Layer

Execution Manager

Order Lifecycle

Broker Factory

Broker Adapter

↓

Infrastructure Layer

Database

Persistence

Broker APIs

Market Data

Scheduler

---

Rules

Decision Engine never executes trades.

Execution never bypasses Risk.

Broker never bypasses Execution.

Dashboards never modify state.

Everything reports upward.