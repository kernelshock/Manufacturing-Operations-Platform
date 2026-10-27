# Domain Event Catalog — Baseline

Status: Draft for G0 validation

Each event must eventually include:
- event_id
- event_type
- schema_version
- occurred_at
- recorded_at
- actor
- source_module
- correlation_id
- causation_id
- tenant/organization
- payload

## Demand / planning
| Event | Producer | Primary consumers |
|---|---|---|
| PlanCreated | Demand | APS, Intelligence |
| PlanReleased | Demand | APS |
| PlanPublished | APS | MES, Intelligence |
| TaquillaImported | Demand | Master Data, APS |
| ProductConfigured | Master Data | APS, Materials |
| ScheduleCalculated | APS | UI, Intelligence |
| SchedulePublished | APS | MES, Intelligence |

## MES
| Event | Producer | Consumers |
|---|---|---|
| OperationStarted | MES | APS, Intelligence |
| OperationCompleted | MES | APS, Materials, Workforce, Intelligence |
| OperationDelayed | MES | APS, Intelligence |
| ProductionTransferred | MES | downstream MES operation, Intelligence |

## Materials / purchasing
| Event | Producer | Consumers |
|---|---|---|
| MaterialConsumed | Materials | Inventory, Intelligence |
| StockAdjusted | Materials | APS, Intelligence |
| StockBelowReorderPoint | Materials | Purchasing, Intelligence |
| ReplenishmentSuggested | Materials | Purchasing |
| PurchaseRequested | Purchasing | Purchasing workflow, Intelligence |
| PurchaseIssued | Purchasing | Materials, Intelligence |
| MaterialReceived | Purchasing/Receiving | Materials, APS, Intelligence |

## Maintenance
| Event | Producer | Consumers |
|---|---|---|
| AssetDown | Maintenance | APS, MES, Intelligence |
| AssetRestored | Maintenance | APS, MES, Intelligence |
| MaintenanceOrderClosed | Maintenance | Intelligence |

## Workforce
| Event | Producer | Consumers |
|---|---|---|
| WorkerAssigned | Workforce | APS, MES |
| WorkerUnavailable | Workforce | APS |
| ShiftChanged | Workforce | APS |

## Intelligence / management
| Event | Producer | Consumers |
|---|---|---|
| KPIThresholdExceeded | Intelligence | Action management |
| ActionCreated | Intelligence/Management | Reporting |
| ActionClosed | Intelligence/Management | Reporting |

## Event rules
- Consumers must be idempotent.
- Events are facts; do not mutate past events.
- Schema changes must be versioned.
- Domain events do not replace synchronous validation inside a transaction.
