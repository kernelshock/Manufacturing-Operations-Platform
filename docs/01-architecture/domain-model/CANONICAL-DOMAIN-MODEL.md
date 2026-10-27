# Canonical Domain Model — Baseline

Status: Draft for G0 validation

## Organizational structure
- Organization
- Plant
- Area
- WorkCenter
- Resource
- Asset

## Product and manufacturing definition
- Product
- ProductVariant
- ProductRevision
- Material
- Subassembly
- BOM / ABM
- Routing
- Process
- Operation
- SetupRule
- Calendar

## Demand and execution
- CustomerOrder
- Plan
- Taquilla
- ProductionOrder
- OperationExecution
- Transfer
- Nonconformance reference

## Materials and purchasing
- InventoryItem
- InventoryBalance
- MaterialMovement
- ReorderPolicy
- KanbanSignal
- Supplier
- SupplierMaterial
- PurchaseRequest
- PurchaseOrder
- Receipt

## Maintenance
- MaintenanceOrder
- DowntimeEvent
- FailureMode
- MaintenanceAction

## Workforce
- Employee
- Skill
- Qualification
- Shift
- Availability
- Assignment
- LaborTime

## Intelligence
- KPI
- Target
- Measurement
- Risk
- Action
- ReportSnapshot

## Cross-cutting
- User
- Role
- Permission
- Configuration
- DocumentReference
- DomainEvent
- AuditEntry

## Modeling rules
1. IDs are internal immutable identifiers; business codes are separate fields.
2. Master data changes are revisioned when they affect production definition.
3. Time is stored with timezone awareness.
4. Units of measure are explicit.
5. Module ownership is explicit for every aggregate.
6. Cross-module references use stable IDs and contracts.
7. Historical execution records are immutable except through auditable correction events.
