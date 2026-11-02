# G3 — Demand / Plan / Taquilla / Routing

Status: **RELEASED**  
Started: 2026-10-29  
Base: released G2 main `115b8dfe11a94d1d2587f5c6937b0383f0f05e65`

## Objective

Turn released G2 manufacturing definitions into governed operational demand without prematurely implementing APS or MES.

G3 introduces the canonical transactional identities for:
- Production Plan;
- Taquilla / production-order demand unit;
- requested product composition per Taquilla;
- vehicle/deck allocation when the source order distinguishes upper/lower floors;
- explicit binding to an approved G2 RoutingRevision;
- historical/administrative lifecycle and source-import provenance.

## Ownership boundaries

### G3 owns
- Plan identity and editable business number;
- Taquilla identity and business code;
- membership/order of Taquillas inside a Plan;
- requested quantities by exact G2 Article;
- optional product configuration context derived from G2, never copied as a competing master;
- simple/double-deck demand structure;
- explicit selected RoutingRevision or governed routing resolution result;
- source-document/import provenance;
- demand lifecycle, cancellation/error correction and historical completion classification.

### G3 does not own
- Article, ProductConfiguration, BOM, Routing/BOP definitions or manufacturing calendars — G2;
- finite-capacity scheduling, resource loading, operation start/end planning, Gantt or what-if — G4 APS;
- actual shop-floor start/finish, produced quantity, scrap or execution trace — G5 MES;
- inventory consumption or replenishment — G6/G7.

## Non-negotiable rules

1. Stable UUIDs are canonical identities. Business numbers may be editable where the process requires it, but editing a number never changes identity.
2. A Plan may contain multiple Taquillas.
3. A Taquilla may contain multiple product Articles and quantities.
4. Product demand references exact canonical G2 Article identities; no duplicated product master is created.
5. Routing selection references G2 RoutingRevision. G3 may bind/resolve a route but cannot mutate the routing definition.
6. Double-deck information is explicit data. Floor assignment is never inferred from document order, product code or description.
7. Imported/legacy records retain source provenance and are idempotent.
8. Removing an erroneous Taquilla is a governed cancellation/void operation once referenced; hard deletion is limited to safe draft records with no dependent evidence.
9. G3 records demand intent and administrative state, not APS schedule timestamps or MES actuals.
10. No business rule may be inferred from legacy code patterns unless its semantics are explicitly validated.

## Planned slices

- **G3.1 — Production Plan & Taquilla Foundation — COMPLETED:** stable identities, editable business numbers, plan→taquilla membership, lifecycle, RBAC, audit and API.
- **G3.2 — Taquilla Product Composition — COMPLETED:** multiple G2 Articles per Taquilla, Decimal requested quantities, ordering and idempotent line identity.
- **G3.3 — Vehicle / Deck Topology — COMPLETED:** SIMPLE / DOUBLE_DECK, explicit UPPER / LOWER allocation and source-document grouping without implicit inference.
- **G3.4 — Routing Binding — COMPLETED:** exact G2 RoutingRevision selection/resolution, effectivity checks and explicit override provenance.
- **G3.5 — Lifecycle & Historical Completion — COMPLETED:** cancellation/error correction plus administrative completion classification for imported historical plans without fabricating MES actuals.
- **G3.6 — Taquilla Assimilation — COMPLETED:** controlled import, duplicate detection, source provenance and validation for one/two-document orders.
- **G3.7 — Operational Projection & Frontend — COMPLETED:** plan/taquilla views and operator workflows needed before APS handoff.
- **G3.8 — Gate Hardening — COMPLETED:** migration integrity, regressions, RBAC/audit, idempotency, security, runtime and release evidence.

## G3 exit criteria

G3 is eligible for VALIDATED only when:
- Plan and Taquilla have stable canonical identities and audited lifecycle;
- plan number remains editable without breaking identity/references;
- one Plan supports multiple ordered Taquillas;
- one Taquilla supports multiple exact G2 Articles and Decimal requested quantities;
- simple/double-deck demand is explicit and validated;
- routing binding uses exact G2 RoutingRevision identities and never copies routing definitions;
- invalid/ambiguous routing resolution is rejected rather than guessed;
- historical completed demand can be represented without inventing MES execution facts;
- source imports are provenance-preserving and idempotent;
- erroneous/cancelled Taquillas are handled without silently destroying referenced history;
- APIs are permission protected and mutations are audited;
- G0/G1/G2 regressions, G3 tests, schema drift, dependency/security audits and runtime regression are green;
- explicit release approval is received before merge/release.

## Current status

**G3 RELEASED**

### G3.8 — Gate Hardening
- hardening implementation head: `627fc2341c5bcd050ab43e0cbf0b58f7e2762b7f`;
- canonical validation: `G3 Demand Plan Taquilla Routing` push run #100 — **SUCCESS**;
- Alembic head remains `0018_g3_6`;
- added explicit gate-hardening invariants for G3 scope/ownership, slice completion, RBAC, mutation audit, assimilation semantics and frontend APS boundary;
- workflow executes the hardening invariant suite separately before the aggregate G3 gate;
- one pre-validation run (#99) correctly failed on a syntax defect inside the new hardening test itself; the defect was corrected before validation and no domain/migration/runtime defect was masked;
- single Alembic head, clean upgrade, `alembic check`, full downgrade to base and replay to head pass;
- G0/G1/G2 regressions and complete G3 suite pass;
- frontend npm audit, typecheck, tests and production build pass;
- secret scan, supply-chain pin checks and Python dependency audit pass;
- released-runtime regression passes;
- aggregate G3 gate passes;
- G3 met all recorded exit criteria and was **VALIDATED** before release;
- explicit release approval received on 2026-11-02;
- PR #9 marked ready and merged to `main`;
- final validated branch head: `00f50cf499d04c209b292a8700c4bfae21991b35`;
- release merge commit: `8bae480b40474a4ac14fa892dec12ea02c51bb08`;
- final PR validation: G3 #111, G0 #153, G1 #166 and G2 #99 — **SUCCESS**;
- G3 status: **RELEASED**.


### G3.7 — Operational Projection & Frontend
- implementation head: `865e07cef52f2534f3c9c6d4567891a94f76adc6`;
- canonical validation: `G3 Demand Plan Taquilla Routing` push run #87 — **SUCCESS**;
- PR validation: G3 #88, G0 #144, G1 #157 and G2 #90 — **SUCCESS**;
- no new migration was required; Alembic head remains `0018_g3_6`;
- added backend operational projection endpoint for Plan → Taquillas → Products → Routing;
- projection resolves Article code/description from G2 and exposes requested quantity, explicit deck, source provenance and exact route-binding state;
- projection publishes aggregate counts for Taquillas, product lines, missing routing and DRAFT blockers;
- introduced permission-driven frontend module `Planificación / Taquillas` for `demand.read` / `demand.edit`;
- frontend shows Plan status, historical classification, ordered Taquillas, topology, products, deck position, routing revision/mode/status and source keys;
- REVIEW_REQUIRED assimilation batches are surfaced as an operator intervention queue;
- `demand.edit` users can submit the normalized G3.6 JSON import contract from the frontend;
- browser import does not parse PDFs or infer product/floor semantics;
- backend remains authoritative for validation and authorization;
- APS scheduling, finite capacity, Gantt and MES actuals remain outside G3.7;
- G0/G1/G2 regressions, G3 suite, frontend typecheck/tests/build, security/dependency and runtime gates pass;
- next slice: **G3.8 — Gate Hardening**.


### G3.6 — Taquilla Assimilation
- implementation head: `6e4f810e8de748fa0db8cd407dc7d0e8960cf427`;
- canonical validation: `G3 Demand Plan Taquilla Routing` push run #52 — **SUCCESS**;
- Alembic head: `0018_g3_6`;
- import uses immutable staging batches before creating operational demand;
- each batch retains source system, parser/mapping versions and deterministic payload fingerprint;
- one or two source documents are supported per Taquilla;
- each source document retains key, filename, SHA-256 and optional export timestamp;
- each imported product line retains source document, source line key, source article identity, quantity and explicit deck position;
- SIMPLE imports require only SINGLE lines;
- DOUBLE_DECK imports require explicit UPPER and LOWER representation;
- a unified document may contain both decks and two documents may map to decks in any order;
- document identity/order never infers floor assignment;
- exact active G2 FINISHED_PRODUCT Article resolution is mandatory;
- unmapped/inactive/non-finished products remain staged with BLOCKER evidence and create no Taquilla;
- source-document reuse, duplicate Taquilla codes, duplicate plan sequences and competing assimilation identities are blocked;
- identical payload replay returns the same batch/target and is explicitly reported as idempotent;
- only a fully validated batch is applied to operational Taquilla/ProductLine records;
- staging provenance points to generated target Taquilla and product-line UUIDs after apply;
- schema drift check and full migration downgrade/replay pass;
- G0/G1/G2 regressions, G3 suite, frontend, dependency/security and runtime gates pass;
- next slice: **G3.7 — Operational Projection & Frontend**.


### G3.5 — Lifecycle & Historical Completion
- implementation head: `1238fdc966a869b75d2d0e6696fdfe49fcd20b8c`;
- canonical validation: `G3 Demand Plan Taquilla Routing` PR run #31 — **SUCCESS**;
- Alembic head: `0017_g3_5`;
- historical Production Plans may be administratively completed as `ON_TIME` or `DELAYED`;
- historical completion bulk-classifies all non-cancelled Taquillas in the Plan;
- historical completion explicitly records that no MES actuals are created;
- administrative historical completion stores actor, classification, note and recording timestamp only;
- no fabricated operation start/end, produced quantity, scrap or shop-floor trace is introduced;
- generic CANCELLED status transitions are blocked in favour of reasoned cancellation endpoints;
- Taquilla cancellation preserves UUID identity and requires an explicit reason;
- Plan cancellation propagates a reasoned administrative cancellation only when no completed Taquilla exists;
- safe hard deletion is limited to DRAFT Taquillas with no product composition and a non-terminal parent Plan;
- Taquillas with dependent composition must be cancelled rather than silently deleted;
- normal Plan completion now requires every Taquilla to be COMPLETED or CANCELLED;
- lifecycle mutations are audited;
- schema drift check and full migration downgrade/replay pass;
- G0/G1/G2 regressions, G3 suite, frontend, dependency/security and runtime gates pass;
- next slice: **G3.6 — Taquilla Assimilation**.


### G3.4 — Routing Binding
- implementation head: `322f8b3b2d73fc72477bd55970acff90bb8ace1a`;
- GitHub Actions: `G3 Demand Plan Taquilla Routing` push run #18 — **SUCCESS**;
- Alembic head: `0016_g3_4`;
- each Taquilla product line may reference one exact G2 `RoutingRevision`;
- automatic resolution follows ProductLine Article → G2 ArticleRevision → ACTIVE/effective RoutingRevision;
- automatic resolution requires exactly one effective candidate across all revisions of the same Article;
- zero candidates returns not-found and multiple candidates are rejected as ambiguous;
- explicit override can disambiguate an exact route but cannot bypass Article ownership, ACTIVE status or effectivity;
- override requires a non-empty reason and persists user/time/effectivity provenance;
- RESOLVED and OVERRIDE binding modes are explicit;
- binding is mutable only while the parent Taquilla remains DRAFT;
- no Routing/BOP definition is copied or modified in G3;
- binding mutations are audited;
- schema drift check and full migration downgrade/replay pass;
- G0/G1/G2 regressions, G3 suite, frontend, dependency/security and runtime gates pass;
- next slice: **G3.5 — Lifecycle & Historical Completion**.


### G3.3 — Vehicle / Deck Topology
- implementation head: `1875a1d73d6d1f93959969584ebc61c718cb71c4`;
- GitHub Actions: `G3 Demand Plan Taquilla Routing` push run #14 — **SUCCESS**;
- Alembic head: `0015_g3_3`;
- Taquilla owns explicit `SIMPLE` / `DOUBLE_DECK` vehicle topology;
- SIMPLE product lines use only `SINGLE`;
- DOUBLE_DECK product lines require explicit `UPPER` or `LOWER`;
- product/document order never determines deck position;
- optional `source_document_key` groups source lines independently from deck position;
- one source document may contain lines for different deck positions and two documents may represent one Taquilla;
- topology may be changed only while the Taquilla is DRAFT and before product composition exists;
- product-line deck/document corrections remain DRAFT-only;
- topology and line mutations are audited;
- initial hardening detected an ORM ownership placement error before release; it was corrected with no physical data rewrite;
- schema drift check and full migration downgrade/replay pass after remediation;
- G0/G1/G2 regressions, G3 suite, frontend, dependency/security and runtime gates pass;
- next slice: **G3.4 — Routing Binding**.


### G3.2 — Taquilla Product Composition
- implementation head: `4f02181630303879b6fd3c8fc827ac09ce37a26c`;
- GitHub Actions: `G3 Demand Plan Taquilla Routing` push run #8 — **SUCCESS**;
- Alembic head: `0014_g3_2`;
- one Taquilla supports multiple ordered product lines;
- each line has a stable UUID identity independent from its sequence;
- each line references one exact G2 Article and accepts only active FINISHED_PRODUCT identities;
- requested quantity uses Decimal(24,8) semantics and must be positive;
- sequence is positive and unique inside each Taquilla;
- optional source_line_key provides source-level idempotency without making product code the line identity;
- identical replay by source_line_key returns the existing line; conflicting replay is rejected;
- product quantity/sequence may be corrected only while the Taquilla is DRAFT;
- READY / COMPLETED / CANCELLED Taquillas freeze product composition;
- Article identity and ProductConfiguration are referenced from G2 and are never copied into G3;
- create/update mutations are audited;
- schema drift check and full migration downgrade/replay pass;
- G0/G1/G2 regressions, G3 suite, frontend, dependency/security and runtime gates pass;
- next slice: **G3.3 — Vehicle / Deck Topology**.


### G3.1 — Production Plan & Taquilla Foundation
- implementation head: `50835bc3f349fb5d7e19991bc4106a237a548859`;
- GitHub Actions: `G3 Demand Plan Taquilla Routing` push run #4 — **SUCCESS**;
- Alembic head: `0013_g3_1`;
- stable UUID identity for ProductionPlan and Taquilla;
- plan business number is editable while non-terminal without changing canonical identity;
- one Plan supports multiple ordered Taquillas;
- Taquilla business code is globally unique and sequence is unique inside its Plan;
- controlled Plan lifecycle: DRAFT → OPEN → COMPLETED, with CANCELLED terminal path;
- controlled Taquilla lifecycle: DRAFT → READY → COMPLETED, with CANCELLED terminal path;
- terminal Plan identity fields are protected from later business-number mutation;
- `demand.read` / `demand.edit` permissions are seeded and ADMIN receives both;
- REST API is protected by server-side RBAC;
- create, number-change and status-transition mutations emit append-only audit evidence;
- schema drift check and full migration downgrade/replay pass;
- G0/G1/G2 regressions, G3 suite, frontend, dependency/security and runtime gates pass;
- next slice: **G3.2 — Taquilla Product Composition**.

