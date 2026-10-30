# G3 — Demand / Plan / Taquilla / Routing

Status: **IN PROGRESS**  
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
- **G3.4 — Routing Binding:** exact G2 RoutingRevision selection/resolution, effectivity checks and explicit override provenance.
- **G3.5 — Lifecycle & Historical Completion:** cancellation/error correction plus administrative completion classification for imported historical plans without fabricating MES actuals.
- **G3.6 — Taquilla Assimilation:** controlled import, duplicate detection, source provenance and validation for one/two-document orders.
- **G3.7 — Operational Projection & Frontend:** plan/taquilla views and operator workflows needed before APS handoff.
- **G3.8 — Gate Hardening:** migration integrity, regressions, RBAC/audit, idempotency, security, runtime and release evidence.

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

## Current slice

**G3.4 — Routing Binding**

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

