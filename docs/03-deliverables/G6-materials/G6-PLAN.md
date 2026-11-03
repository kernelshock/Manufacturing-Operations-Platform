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

## FAIC procurement, lead-time variability and safety-stock requirement (2026-11-03)

**Explicit user requirement; binding for G6.5/G6.6 and G7 Kanban/Procurement.** Safety-stock, reorder-point (P.P.) and replenishment-quantity (C.R.) models MUST account for late deliveries, not just the contractual supplier lead time. The calculations must link:

- **G2 canonical material or manufactured subassembly** (article ID, revision, unit, alternatives, supplier-article map, supplier code shared with Prolowin/CRM), and effective multi-level BOM quantity and scrap to all finished-product families that use the item. Shared materials are aggregated only once per distinct underlying demand; avoid double-counting manufactured intermediate assemblies alongside their exploded inputs.
- **G3 demand / G4 published planning / G6.3 theoretical BOM explosion**, with dated requirements, selected demand horizon and actual G5/G6.4 consumption history. Preserve the distinction between forecast demand and measured use and allow evaluation over selectable historical date ranges.
- **Purchasing and supplier service level**: supplier-specific AND article-specific agreed lead time (business days), order date, confirmed/actual arrival date, promised vs actual lead time, late days, partial deliveries, open purchase orders, outstanding quantities, reliability/variability over time, calendar/holidays and supplier alternatives. Internal manufacturing lead times and bottleneck/capacity must be modeled separately for manufactured subassemblies; don't treat them as external purchase orders.
- **Stock position**: known on-hand by location, reserved, quality-blocked/non-usable, in-transit and pending confirmed purchase receipts. A pending PO cannot be counted as physically received. Operational stock and Prolowin accounting balances remain reconciled, not silently conflated.
- **Security and replenishment policy**: configurable service level, demand variability, effective replenishment lead-time distribution and observed lateness; the existing FAIC Kanban 25% security percentage can be supported as a configurable baseline/simplified policy, never silently substituted for a variability-based safety stock. P.P. = expected demand during effective replenishment lead time + safety stock, with clearly identified calculation method, time base and units. C.R. supports fixed or calculated approaches, MOQ/pack multiples, and selectable manual/inventory on-hand sources. Both per-product and per-seat consumption bases must remain switchable.
- **Audit and decision trace**: explain every recommendation with source records and dates (BOM revision, consumption window, supplier delivery evidence, pending orders, calendars and stock snapshot), show data-quality limitations, simulate stockout risks and supplier-delay scenarios, and leave PO issuance to authorized G7 purchasing workflow.

**Acceptance constraints:** Supplier delay cannot be inferred from a single agreed lead-time field; use historical order/receipt evidence when available. Missing arrival data remains UNKNOWN (or marks a calculated default as ASSUMPTION), not zero delay. Business-day calendars must be explicit. Aggregate shared-component demands across applicable products but do not double-count coexisting forecast/actual records. Price/lead-time choices must not bypass approved suppliers, purchase authorization or quality requirements.

**Delivery milestones:** G6.3 only produces source-traceable **theoretical** material requirements; G6.4 links actual consumption; G6.5 incorporates reservations and usable stock; G6.6 stages Prolowin purchase/receipt/supplier data with traceable identity and no automatic overwrite. **G7** computes safety stock, P.P., C.R. and purchasing recommendations under the policy above. No purchases or inventory movement are authorized by demand calculations alone.

