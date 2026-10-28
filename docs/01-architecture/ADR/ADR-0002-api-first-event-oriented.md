# ADR-0002 — API-first and Event-oriented Contracts

Status: Accepted  
Date: 2026-10-27

## Context
The platform must progressively integrate APS, MES, materials, purchasing, maintenance, workforce, future ERP adapters and later industrial edge/PLC connectivity.

## Decision
All module capabilities must be expressible through explicit application/API contracts. Cross-module state propagation should use domain events where asynchronous coupling is appropriate.

Initial events include:
- PlanCreated
- PlanPublished
- OperationStarted
- OperationCompleted
- MaterialConsumed
- StockBelowReorderPoint
- PurchaseIssued
- MaterialReceived
- AssetDown
- AssetRestored
- WorkerAssigned
- KPIThresholdExceeded

## Consequences
- UI is not the business logic boundary.
- Integrations can reuse the same application contracts.
- Event handlers must be idempotent.
- Events require versioned schemas and audit metadata.
