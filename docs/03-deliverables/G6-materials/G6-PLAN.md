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
| **G6.5 — Reservations / Availability** | **IMPLEMENTED, final SHA CI pending:** immutable HOLD/RELEASE by taquilla and BOM leaf, stock and demand limits, concurrency locks, unallocated stock and shortage projection; no automatic stock issue |
| **G6.6 — Prolowin Assimilation (legacy/manual-first)** | **IMPLEMENTED / CI pending:** screenshot PNG/JPEG + manual transcript, original-source fingerprint, two-person verification, PO / partial receipts / claims / reschedules / supplier-risk escalation, reconciliation without API or export dependence |
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

## G6.5 — Reservation / Availability acceptance contract

**Implementation:** `migrations/versions/0032_g6_5_reservations.py`, `src/mop/materials/reservation_models.py`, `reservation_schemas.py`, `reservation_service.py`, `src/mop/api/v1/materials.py`, `tests/g6/test_reservations_integration.py`. **Development only**, PR #14 stays DRAFT.

- A G6.5 `HOLD` is an explicit, audited physical allocation to one G3 taquilla, for a terminal purchased/consumable material present in the effective G6.3 BOM explosion. It records plan, taquilla, article, location, canonical UoM, exact quantity, BOM effective timestamp, actor, source reference and idempotency key. It is **not** an inventory ISSUE, purchase commitment, MES consumption or automatic reserve from APS.
- The total still-held quantity for each taquilla/article across locations **cannot exceed its effective BOM need**. Multiple taquillas that share one material compete for the same physically counted stock: reservations serialize using PostgreSQL advisory locks. Holds cannot exceed unallocated physical on-hand at the specific location. Unknown inventory is not assumed to be zero or sufficient.
- Each `RELEASE` is an append-only, reason-coded event linked to the original hold, with independently idempotent evidence. Partial release is supported; a release above the remaining allocated quantity is rejected. Original reservations and release history cannot be directly updated/deleted, enforced by PostgreSQL trigger and positive/negative signed constraints.
- Location `availability` reports **on_hand**, **reserved**, and **unallocated_on_hand = on_hand − reserved** (or UNKNOWN). It is explicitly labeled `PHYSICAL_UNALLOCATED_NOT_QUALITY_CERTIFIED`. The operation does not infer quality-released, available-to-promise, in-transit, booked receipt, or incoming Prolowin quantities. **Never present unallocated physical stock as certified usable stock.**
- Taquilla `coverage` relates a dated G6.3 theoretical material requirement to that taquilla's commitments and a requested location's unallocated physical quantity. It reports a provisional shortage, or UNKNOWN when physical inventory has not been initialized. **Location-scoped coverage cannot be summed across locations or multiple taquillas** without an allocation/coverage aggregation engine; one unallocated physical quantity cannot satisfy multiple independent taquillas twice.
- Generic stock `ISSUE`, reduction by receipt reversal and G6.4 actual consumption respect all active location holds. Consumption **requires an explicit reservation release first**: no implicit commitment fulfillment, hidden stock deduction or bypass of another taquilla's reservation. Retain the reason and source for the release and the distinct G6.4 measured consumption.
- Cancelling a taquilla or plan does **not silently erase existing holds**: the responsible Materials actor must perform an explicit, audited release. New holds to cancelled plans/taquillas are prohibited. If BOM or product quantities change after a hold, previous evidence is immutable and commitments must be reviewed/released and, where appropriate, re-allocated against the effective revision.
- Reservations of internally manufactured *intermediate assemblies* are **not automatically inferred** from terminal material BOM explosion; manufactured assemblies need a distinct confirmed stock/netting policy before safe multi-level supply allocation. G7 also requires explicit Quality stock status and inbound Prolowin PO/partial receipts before true available-to-promise and lead-time risk projections.

### G6.5 API contract and validation

- `POST /api/v1/materials/reservations` — create a measured `HOLD`, `materials.edit`.
- `POST /api/v1/materials/reservations/{hold_id}/release` — release part/all, `materials.edit`.
- `GET /api/v1/materials/taquillas/{id}/reservations` — append-only evidence history, `materials.read`.
- `GET /api/v1/materials/availability?article_id=...&location_id=...` — physical unallocated, `materials.read`.
- `GET /api/v1/materials/taquillas/{id}/coverage?article_id=...&location_id=...&effective_at=...` — provisional BOM/coverage and shortage, `materials.read`.
- Required acceptance: Alembic single head `0032_g6_5`, upgrade/check/downgrade/reinstall/check, PostgreSQL immutable-event protection and forged-sign checks, simultaneous allocations, replay/conflict, partial release, known/unknown stock, cancellation, negative/over-reservation guards, stock ISSUE protection, authenticated HTTP RBAC; G0–G6 **all SUCCESS on final identical branch SHA**.

**Procurement linkage:** the original and revised delivery commitments, partial receipts, claims, actual lateness and alternate sourcing decisions confirmed for Prolowin remain requirements for G6.6 and G7. They are not hidden inside G6.5 physical stock availability; no safety-stock calculation or purchase execution is introduced at this stage.


## G6.6 — Legacy Prolowin / Manual-First Procurement Assimilation

**User-confirmed constraint (2026-11-04):** Prolowin is old and closed. Do **not** assume a REST API, database connector, stable Excel/CSV exports, screen scraping or OCR. Primary viable source is **operator-entered transactions from screens**, with optional **original screenshot attachments** for independent verification. A thin weekly Excel log is only secondary supporting evidence and can have incomplete transaction history.

### Workflow and roles

1. **Identify source.** Operator creates a MANUAL evidence source with a screen/reference label, or uploads an original PNG/JPEG screenshot (4 MiB maximum). The screenshot is stored in the application DB, inaccessible without `prolowin.procurement.read`, with immutable SHA-256 fingerprint and read-only binary. No automatic OCR or data extraction is assumed. Weekly Excel snapshot may be registered only as secondary evidence.
2. **Transcribe and stage.** Operator with `prolowin.procurement.capture` enters original PO line, receipt/delivery note (including partial), original promise/reprogramming history, claims, and production-risk escalations. Each entry is `PENDING`, references the capture and records precise unique source key, supplier and article codes, quantity, unit, date, source document/reference and author. Duplicated source keys reject rather than duplicate open receipts.
3. **Verify independently.** A *different user* with `prolowin.procurement.verify` verifies or rejects by comparing with original Prolowin screen/source. Verification requires an active unambiguous G2 supplier/article/canonical UoM mapping and a previously verified original order for subsequent events; receipts cannot exceed ordered quantity. Weekly snapshot alone cannot establish a verified procurement transaction. The decision and reviewer identity are audited. No production or purchasing side effects.
4. **Read trusted history.** `prolowin.procurement.read` can consult original promises, latest accepted reprogramming, partial receipt count, delivered quantity, accepted quantity when explicitly recorded, open delivery quantity, claims and alternate-supplier escalation indicators, all derived **only from verified records**. For fully delivered orders, lateness is assessed against the last actual receipt; for open orders, against the as-of date. Calendar-day figures are explicitly provisional and **not business-day lead-time** until G7 calendar policy is applied.

### Data boundaries and controls

- No API, direct database access, credentials, privileged integration with Prolowin or reliable Excel structure required.
- Original PO promises are immutable; accepted reschedule requires explicit no-risk-for-production confirmation and reason. If production is at risk, capture an ESCALATION to evaluate alternative suppliers; do not silently reprogram, change supplier, or create PO.
- Delivery `quantity` is not automatically `accepted_quantity`: Quality accepted quantity is NULL/UNKNOWN unless evidenced. A delivery note or screenshot **does not post G6 physical inventory**, reconcile accounting stock or imply receipt acceptance.
- All supplier and article values retain source codes; only independently verified mapped records contribute to operational procurement summaries. Unmapped items stay PENDING or REJECTED, not silently discarded.
- Manual snapshots are **incomplete by nature**; no claim of an exhaustive PO register, global outstanding liabilities or real-time ERP synchronization. The summary is a verified sample with explicit provenance, not authoritative completeness or ATP.
- Payload and screenshot source are immutable in PostgreSQL (review status transitions only, with author/reviewer attribution and audit). Corrections require new evidence and documented disposition; no deletion of underlying original screen/capture. Passwords or unrelated personal records should be excluded/redacted from screenshot before upload under approved FAIC evidence policy.
- Excel/CSV ingestion may be added later *only if a feasible export is identified*, with semantic mapping, source hashes and cross-snapshot deduplication; it is **not** a prerequisite to G6.6 technical acceptance. G2 BOM structure assimilation remains separate.
- Data quality: missing original promises/line identity, missing or duplicate receipt reference, mismatched supplier/article/UoM, over-receipt, missing source reference or unknown Quality acceptance must fail closed for verified analytics.

### Implementation and planned acceptance

- `src/mop/prolowin/procurement_models.py`, `procurement_schemas.py`, `procurement_service.py`, `src/mop/api/v1/prolowin_procurement.py`.
- Alembic `migrations/versions/0033_g6_6_legacy_procurement.py` adds captures and source-evidenced immutable transcriptions, independent IAM and full rollback.
- `frontend/src/shell/ProlowinCapturePanel.tsx` presents source upload/manual entry, transaction type, order-line fields, review controls and verified history. Navigation via `Compras · Prolowin` (not G7 purchasing).
- `tests/g6/test_prolowin_procurement_integration.py` covers no-API round trip, original screenshot magic/size, SHA duplicate, independent verification and self-review denial, PO and two partial receipts, explicit accepted quantity, original/revised promise preservation, claims, risk escalation, duplicate evidence, unmapped IDs, over-receipt, weekly-secondary refusal and **no G6 stock movements**.
- G6.6 is **IN VERIFICATION** until final same-SHA G0–G6 workflow successes and frontend typecheck/browser testing. No G6 RELEASED, no main merge, no production deployment or live FAIC data loaded.

### Future use

G7 may calculate supplier delivery reliability, safety stock, PP/CR and supply-risk alerts only from sufficiently complete, high-confidence history, annotated with coverage and missing-data caveats. Do not equate absent claim/receipt records with none having occurred. Business-day calendar and internal manufactured-subassembly replenishment paths stay explicit.
