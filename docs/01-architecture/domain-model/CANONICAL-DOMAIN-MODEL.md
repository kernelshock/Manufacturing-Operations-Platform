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
- ReplenishmentLoop
- PointOfUseContainer
- KanbanCard
- ReplenishmentCycle
- ReorderPolicy
- KanbanSignal
- Supplier
- SupplierMaterial
- PurchaseRequest
- PurchaseOrder
- Receipt
- ReceivingInspection

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


## Kanban relationships

```text
Material 1 --- n ReplenishmentLoop
ReplenishmentLoop 1 --- 1 KanbanCard
ReplenishmentLoop 1 --- n PointOfUseContainer
ReplenishmentLoop n --- n Product
ReplenishmentLoop n --- n Area/WorkCenter
KanbanCard 1 --- n ReplenishmentCycle
```

A `ReplenishmentLoop` represents the physical supply circuit whose consumers share one reorder policy. Its PP and replenishment quantity are local to that loop, even when the same material exists in other loops.


## Recursive product structure and routing

The canonical model must support:

```text
Article / ProductRevision
  |
  +-- ComponentRelation(parent, child, quantity, unit_of_measure)
  |       |
  |       +-- child may itself be another manufactured Article
  |
  +-- Routing
          |
          +-- Operation
                  |
                  +-- ResourceAssignment
```

BOM/ABM depth is not fixed.

Imported operations/resources must be classified before APS scheduling so that costing-only pseudo-operations and pseudo-resources are excluded from physical capacity.


## Prolowin complete-structure normalization

Prolowin complete-structure reports can repeat the same article code across multiple operation stages and the final state. Therefore the ingestion layer must preserve a source-row representation before normalization:

```text
SourceStructureRow
- parent_article_code
- article_code
- operation_code
- source_description
- quantity
- source_uom
- source_timestamp
```

These source rows are normalized into canonical Article, ComponentRelation, Operation and ArticleOperation entities. Repeated operation rows must not be naively summed as independent material demand.


## Configuration-specific BOM rule

Product-family membership does not authorize BOM inference.

The canonical BOM/ABM must be effective against the **exact ProductRevision/Configuration**. Cross-variant multipliers may be analyzed for validation or optimization, but they are not a substitute for an explicit source structure.


## Prolowin ingestion/reconciliation entities

```text
RawImportBatch
  -> SourceStructureRow
       -> SourceOperationState        (non-FIN source rows)
       -> FlattenedArticleRequirementSnapshot (validated FIN projection)

Article
  -> ArticleClassification
  -> UomMapping / canonical UoM

BOMRevision
  -> ComponentRelation

RoutingRevision
  -> Operation
  -> ArticleOperation
  -> ResourceAssignment

DataQualityIssue
```

The same canonical `Article` is global and may be reused by many finished-product BOMs. Product ownership is expressed by relations, not duplicated article records.

The flattened FIN projection is a reconciliation snapshot; it does not replace the recursive BOM hierarchy.
