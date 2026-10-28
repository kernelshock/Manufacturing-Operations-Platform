# ADR-0011 — Separate BOM/ABM from BOP/Routing

Status: Accepted  
Date: 2026-10-28

## Context
Three complete Prolowin reference products (X-1148, X-1149 and X-2209) show that the source mixes:
- component/material structure;
- intermediate manufactured articles;
- operation stages;
- final states.

X-2209 provides direct evidence that one manufactured article (A-208) traverses several productive processes before FIN.

## Decision
MOP will maintain two separate but linked canonical structures.

### BOM / ABM
Defines **what is required**:
- parent article/revision;
- child article/material;
- quantity;
- unit of measure;
- effectivity/version.

### BOP / Routing
Defines **how the manufactured article is produced**:
- ordered operations;
- canonical process/area;
- work center/resource;
- nominal performance where available;
- effectivity/version.

Both structures are linked through the same manufactured Article/ProductRevision, but they are not stored as one flattened table.

## Source normalization rule
Prolowin operation-coded rows are preserved in staging. They are classified into routing/operation information and are not naively added to material consumption.

`FIN` represents a source completion/final state unless a specific physical operation is independently validated.

## Consequences
- Materials explodes BOM/ABM only.
- APS schedules validated BOP/routing operations only.
- MES executes and records those operations.
- complete Prolowin reports can be used for reconciliation of both structures.
- source mappings remain configurable because operation labels/codes may vary.
