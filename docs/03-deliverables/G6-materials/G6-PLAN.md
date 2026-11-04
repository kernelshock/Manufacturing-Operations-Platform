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
| **G6.4 — Actual Material Consumption** | **IMPLEMENTED — CI acceptance pending final HEAD:** explicit G5 operation-bound material use, atomic stock ISSUE, append-only reversal/correction, Decimal/UoM, actor/time/source evidence, IAM and idempotency |
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

## Confirmed FAIC Prolowin procurement workflow — source-of-record clarification (2026-11-03)

**Confirmed by FAIC for G6.6 Prolowin Assimilation and G7 Kanban/Purchasing** (functional behavior, not yet a verified API/schema specification):

1. **Prolowin is the primary transactional record.** Purchase orders contain the order date, promised delivery date, actual receipt dates and **partial supplier deliveries**. It also records supplier claims after delivery noncompliance and delivery rescheduling/reprogramming.
2. **Reprogramming is conditional on production continuity.** When delivery can be rescheduled without placing production at risk, an agreed new date is recorded. When the situation threatens production, purchasing begins searching for **alternative suppliers**. This is an escalation workflow, not an automatic authorization to place a substitute purchase order or to replace an approved supplier.
3. **A weekly Excel export is only a secondary historical snapshot/log** of operations, claims or pending deliveries from that week. It is *not* a competing system of record, nor a full transaction source. Preserve file date, export provenance and snapshot relationship to Prolowin; do not sum snapshots as new receipts, new orders or new claims.

### Minimum conceptual mapping (verify actual Prolowin identifiers and column names before integration)

- **Purchase-order header:** unique Prolowin PO ID/number, supplier ID/code, order date, buyer/status.
- **PO line:** unique line ID, canonical G2 article/supplier-article code, unit, quantity ordered, original promised date, active revised promised date, line status.
- **Delivery/receipt events:** stable receipt or delivery-note ID and PO-line linkage, actual timestamp/date, received quantity, accepted/rejected quantity when available, partial receipt number, cumulative received and outstanding quantity. Do not mistake a delivery note for verified physically accepted stock.
- **Reprogramming history:** PO/line association, old promised date, new promised date, date of change, documented reason, approving user when available, and whether production continuity was assessed as safe. **Never overwrite original promised date:** retain *original commitment*, each accepted revision and actual receipt separately.
- **Claims and noncompliance:** claim ID, PO/line and supplier linkage, opened/closed timestamps, reason and severity, corrective follow-up, resolution. Claims are evidence of supplier service quality, not physical receipts or new purchase orders.
- **Production-risk and alternate-source escalation:** affected materials/subassemblies, dated G3/G4 needs, usable G6 inventory and outstanding orders, predicted stockout date, risk classification, supplier-alternative evaluation and approval state. Respect PG-10, supplier quality requirements and authorized purchasing decisions.

### Lead-time and risk calculation semantics

- Calculate **actual lead time** by PO line and receipt event from *order date* to the respective accepted receipt date using a documented **business-day calendar**. For partial receipts, also calculate quantity-weighted service and **date of full fulfillment**, not just first delivery.
- Calculate **lateness against the original promised date** and, separately, **lateness against the latest approved revised date**. A reprogramming must **never erase the original missed commitment** from supplier reliability metrics. The accepted revised date may be used for near-term coverage forecasts, identified as a revised assumption with its revision history.
- For open orders, classify outstanding quantity and **current overdue days**, but do not infer an actual arrival date or count open deliveries as received. Missing dates remain UNKNOWN and are flagged for data quality.
- Account for multiple simultaneous open PO lines, partial receipts, goods blocked by Quality, calendars, supplier-specific actual delay distributions and internal lead times for manufactured subassemblies.
- Compute production disruption risk from **dated BOM-derived needs, usable stock, reservations, expected receipts, and coverage** rather than from the fact that a supplier is late alone. Generate an escalation/alternative-supplier evaluation when continuity is threatened; the engine must not automatically switch supplier, amend orders or bypass purchasing approvals.
- Supplier scorecards must show on-time complete delivery, original-vs-revised commitment performance, quantity-weighted partial-delivery performance, claim frequency and aging, lead-time variance and production-risk incidents. Keep the evaluation traceable to immutable IDs and dates.

### Integration acceptance and remaining discovery

G6.6 will use a read-only, staged ingestion with original Prolowin IDs, source hashes, incremental history, duplicate detection and reconciliation. The weekly Excel files may provide corroboration or historical backfill with explicitly marked confidence, **not independent stock posting or supplier-delay events**. Before implementation, inspect the actual Prolowin export schema or interface and confirm that original promised dates and reprogramming versions remain retrievable, how claims and partial receipts are keyed, and how accepted stock differs from delivered stock. The confirmed functional capabilities do not establish the exact database structure or authorize direct access.

**Scope:** G6.3 remains a read-only BOM theoretical-demand projection, G6.4 will capture actual material consumption, G6.5 usable/reserved stock, G6.6 Prolowin purchase/receipt/claim/reprogram evidence, and G7 governed safety stock, P.P., C.R., supplier delay analytics and alternative-source recommendations. No production access or purchasing action is authorized by this clarification.


## G6.4 — Actual Material Consumption / acceptance evidence

- **Authority:** Only an explicit POST with `materials.edit` and measured operator evidence creates a G6 consumption record. G5 START/PAUSE/COMPLETE and the theoretical G6.3 BOM explosion **never** generate a stock issue implicitly.
- `src/mop/materials/consumption_models.py` + Alembic `0031_g6_4`: immutable `mat_consumption` events (`CONSUME`/`REVERSE`), unique idempotency and reversal links, source timestamp, actor, source reference, G5 `execution_operation_id` and unique G6 stock movement link. PostgreSQL trigger prevents direct modification or deletion.
- `src/mop/materials/consumption_service.py`: validate released MES dispatch with operation started, active purchased/consumable/manufactured input, canonical UoM, measured observation within actual operation interval, known sufficient stock, exact positive Decimal; PostgreSQL row/advisory locks protect concurrent posting. Each explicit consumption atomically inserts an `ISSUE`, immutable consumption evidence and audit records under **one database COMMIT**. Failure leaves no partial stock/evidence.
- Source-namespace guard: generic inventory posting cannot impersonate G6 consumption events. Generic movement reversal cannot bypass the linked G6 consumption correction route. Corrections append `REVERSE` and linked stock reversal with **required reason and timestamp**; no rewriting G5 execution, G2 BOM or prior inventory events.
- `src/mop/api/v1/materials.py`: `POST /operations/{id}/consumptions`, `GET /operations/{id}/consumptions`, `POST /consumptions/{id}/reverse`. Read/write IAM roles remain distinct. Duplicate requests with identical evidence are idempotent; conflicting evidence returns 409; malformed/negative/float quantities return 422.
- `tests/g6/test_actual_consumption_integration.py`: real published G4 → released G5 dispatch, MES START, material stock opening, measured consumption, correction, audit actor, stock conservation, direct SQL UPDATE/DELETE rejection, unauthorized bypass, API RBAC and invalid data. No FAIC production inventory is used.
- G6 #78 on the implementation commit verified **29 tests passed**, clean PostgreSQL 18 Alembic migration upgrade/downgrade/replay/schema comparison and security checks. Full same-SHA G0–G6 regression and final documentation HEAD verification remain required for technical acceptance.
- **Boundary:** the link to G6.3 BOM and G3 taquilla is via the canonical G5 operation/product_line/plan foreign keys. Planned BOM quantity and actual consumption remain separate. Material/BOM variance projections and presentation belong to G6.7; reservations and available-to-promise to G6.5; Prolowin receipt/PO synchronization to G6.6. G7 owns safety stock/P.P./C.R., inclusive of actual supplier delays and reprogramming evidence.
- **Governance:** G6 remains IN PROGRESS. No PR #14 merge, G6 RELEASED, automatic FAIC inventory import or production deployment is authorized.
