# G6 — Materials + ABM/BOM

**Status:** OPEN / IN PROGRESS. **Branch:** `feat/G6-materials`. **Baseline:** `main` at `779dfac01c2b64f17120f56119a991865c67be67` (G5 RELEASED).

## Objective

Extend the canonical G2 material/BOM records with operational materials management without merging theoretical demand, actual consumption, ERP accounting stock, or purchase commitments into a single undocumented number. G6 closes with a demonstrable, audited material balance, demand and consumption traceability, and controlled interoperability. **Kanban, reorder points, replenishment proposals and purchasing remain G7**.

## Increment plan

| Increment | Contract / acceptance evidence |
| --- | --- |
| **G6.1 — Materials Domain & Ownership Foundation** | Exact quantitative semantics, source-of-record boundaries, immutable stock ledger principle, strict Decimal/UoM validation, deterministic material reconciliation primitives; unit tests |
| **G6.2 — Stock Locations & Balances** | **IMPLEMENTED / CI verification pending final SHA:** warehouse/location, immutable PostgreSQL ledger, zero/unknown opening, posted movements, reversals, on-hand projection, idempotency, audit and RBAC REST endpoints |
| G6.3 — Material Demand / BOM Explosion | Approved BOM revision + effectivity + G3 plan/taquilla quantities; theoretical demand by source and date; no inferred consumption |
| G6.4 — Actual Material Consumption | Explicit allocation to G5 execution operation; measured quantity, event evidence, reversals/corrections; prevent double booking |
| G6.5 — Reservations / Availability | Reservations, release, shortage and availability checks; no invisible inventory deduction from APS schedule |
| G6.6 — Prolowin Inventory Assimilation | Staging, mappings, deduplication, reconciliation and discrepancy approval; accounting ERP data remains its own source of record |
| G6.7 — Materials Projection & Frontend | Material cards, consumption vs theoretical, location ledger and variance with permissions; printable/report-ready summaries |
| G6.8 — Gate Hardening | One-SHA G0–G6 CI, migrations/rollback, domain invariants, RBAC, real browser E2E and explicit release decision |

## Data ownership

- **G2 Master Data** owns Article, UoM, approved BOM Revision/Line, supplier mappings and revision/effectivity.
- **G3** owns customer demand, plan, taquilla and product composition.
- **G4 APS** owns predicted requirements, published schedules and capacity projections; scheduling does not decrement stock.
- **G5 MES** owns measured execution quantities/times, scrap, resource, operator, event/audit evidence; a completion event is not automatically proof of material consumption.
- **G6 Materials** owns physical location-based stock movements, operational stock balance and consumption records after a specifically approved event. A physical receipt, movement or reversal needs source id and audit actor.
- **Prolowin/ERP** remains authoritative for accounting inventory and purchase commitments until a documented integration authority is approved; imports are staged and reconciled, not overwritten.
- **G7** owns purchase decisions, Kanban PP/CR and replenishment signals; G6 may expose read-only shortfall facts, but does not raise purchase orders.

## Hard invariants

1. Balances derive exclusively from immutable signed ledger movements; never mutate a historical movement to change stock. Correction is a linked reversal plus a new movement.
2. One idempotency key per source event; equal evidence may replay without duplicate movement; different evidence on the same key conflicts.
3. Positive, finite, dimension-consistent Decimal quantity with explicit canonical UoM. No float arithmetic, no implicit conversions of length/mass/count or silent unit substitution.
4. Unknown stock and zero stock are distinct. Material demand cannot be counted as stock issue; receipt cannot be counted until accepted.
5. No direct mutation of G2 BOM, G3 demand, G4 schedule or G5 execution from Materials.
6. Inventory source segregation (operational vs accounting) is explicit and reconciled through auditable actions.
7. Every stock posting records actor, site, article, location, source and effective time. No negative stock unless an explicit approved policy permits it.
8. Reserved, on-hand, available and on-order quantities remain distinct, with traceable provenance.
9. No FAIC production data is imported or written during G6 development. Test fixtures are isolated and disposable.

## G6.1 scope

Establish a deterministic reconciliation kernel for comparison of theoretical demand vs actual consumption and bounded on-hand stock, with Decimal quantities and explicit unknown-state treatment. This **does not yet book stock movements**. G6.2 introduces durable ledger and database migrations. G6.1 accepts pure unit-tested evidence only and must not be marked G6 RELEASED.

## Open integration policy decision

The technical design supports Prolowin as a separate upstream source. Before G6.6 goes live, FAIC must confirm whether its stock records are the official accounting source and how they can be accessed (CSV/XLSX/API/DB), which imports are read-only, and whether operational inventory should be mastered by MOP. No guess is incorporated into production data or imports.

## G6.2 — Implementation and gate evidence index

- `migrations/versions/0030_g6_2_locations_balances.py`: one Alembic head extending the released G5 schema, stock-location tables, PostgreSQL append-only UPDATE/DELETE rejection trigger, deterministic unique Materials IAM permissions.
- `src/mop/materials/models.py`: warehouses linked to G1 plants; nested locations; signed, immutable postings referencing G2 article/UoM; actor, source, timestamp and reversal linkage.
- `src/mop/materials/service.py`: PostgreSQL advisory transaction locks for concurrent postings; fail-closed negative-stock guard; exact Decimal; idempotent replay vs evidence conflict; reversal as a distinct entry; audit event in the same database transaction.
- `src/mop/api/v1/materials.py`: authorized warehouse/location CRUD creation and listing, stock movements, reversal, balance, ledger queries with `materials.read` and `materials.edit`.
- `tests/g6/test_locations_balances.py`: actual PostgreSQL invariants, including unknown vs known-zero balances, reversal and direct SQL append-only enforcement.
- `tests/g6/test_materials_api_integration.py`: FastAPI REST authentication, operator-reader segregation, audit, balance, replay and no unauthorized mutations.
- `.github/workflows/g6-materials.yml`: PostgreSQL 18 fixture, migration upgrade/downgrade/replay, Alembic schema check, G6 contract tests and repository security checks.
- **Validation criterion:** G6.2 can be accepted as technically demonstrated only after G6 Actions and G0–G5 independent workflows pass on the same final branch SHA. These tests create only disposable CI records. No operational inventory from FAIC or Prolowin is imported, and no production deployment is authorized.
- **Scope boundary:** G6.2 establishes durable on-hand quantities and governed postings. Reservations, ATP/available-to-promise and reconciliation of Prolowin balances belong to G6.5/G6.6, respectively; consumption measured against G5 belongs to G6.4. An MES completion does not cause an implicit stock movement.
