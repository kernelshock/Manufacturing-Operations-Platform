# ADR-0008 — Legacy PP/PR Values Are Non-authoritative

Status: Accepted  
Date: 2026-10-27

## Context
FAIC historically calculated reorder points in `Calculo de Punto de Pedido_V01_R01-MXZ.xlsx`.

The workbook contains useful domain logic linking:
- product/model consumption;
- expected demand;
- supplier replenishment time;
- safety factor;
- reorder point.

However, the supporting data flows have become obsolete or broken. Current physical Kanban values and workbook outputs no longer reconcile reliably.

## Decision
The historical workbook is retained as a **reference model**, not a current source of operational PP/PR truth.

Existing PP and replenishment quantities must be marked as legacy values until recalculated and approved under a new versioned `ReorderPolicy`.

MOP must preserve the useful concept:
```text
material demand during replenishment exposure + safety protection
```
while replacing stale inputs with controlled, current and auditable sources.

## Required behavior
- never silently overwrite a physical card from a calculated proposal;
- show current physical-card value and proposed recalculated value side by side during migration;
- record variance and projected inventory/cost impact;
- require approval before a new policy becomes effective;
- keep historical policy versions for traceability.

## Consequence
Recalibrating PP/PR becomes a measurable improvement program rather than a simple data migration.
