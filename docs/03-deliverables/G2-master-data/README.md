# G2 — Master Data

Status: **VALIDATED**  
Started: 2026-10-29  
Base: released G1 main `ac8e27f7596fda999f17253a646c06386ed1cfae`

## Objective
Implement the canonical manufacturing-definition owner defined in G0 so later APS, MES, Materials and integration gates consume one versioned source of truth.

## Non-negotiable architecture
- Master Data owns Article, ArticleRevision, UoM, product configuration, BOM and Routing/BOP definitions.
- Materials consumes BOM; APS consumes Routing/BOP; MES executes approved revisions.
- Core G1 owns Organization/Plant/Area/WorkCenter/Resource; Master Data references those resources and does not duplicate them.
- Prolowin imports pass through immutable staging/validation before canonical application.
- quantities use Decimal semantics;
- source UoM text is preserved;
- manufacturing definitions are versioned and not silently overwritten;
- raw proprietary FAIC evidence remains outside this public repository.

## Planned slices
- **G2.1 — Article & UoM foundation — COMPLETED:** Article, ArticleRevision, UoM, UoM aliases, RBAC, audit and API.
- **G2.2 — Product configurations — COMPLETED:** commercial/manufacturing configuration metadata tied to exact Article identity, dimension-safe width and permission-driven frontend visibility.
- **G2.3 — Supplier master — COMPLETED:** canonical supplier identity, Prolowin/CRM source mappings and Article sourcing data for purchasing/material flows.
- **G2.4 — BOM — COMPLETED:** revisioned BOM, immutable published component structures, Decimal-safe recursive explosion, effectivity, path provenance and cycle detection.
- **G2.5 — Routing/BOP — COMPLETED:** revisioned Routing/BOP, operation semantics, effectivity and references to G1 Area/WorkCenter/Resource identities.
- **G2.6 — Calendars/effectivity — COMPLETED:** versioned manufacturing calendars, hierarchical Plant/Area/WorkCenter/Resource resolution, weekly capacity windows, dated exceptions and historical effectivity.
- **G2.7 — Prolowin assimilation — COMPLETED:** immutable staging, FIN normalization, routing evidence separation, direct parent-child candidate BOMs, DQ quarantine and canonical reconciliation.
- **G2.8 — Gate hardening — COMPLETED:** migration drift detection, full downgrade/replay, regression corpus, dependency/security gates, runtime validation and release-facing evidence.

## G2 exit criteria
G2 is eligible for VALIDATED only when:
- canonical Article identity and revisions are persisted and audited;
- UoM raw-source mappings are preserved and governed;
- product configurations and supplier master are operational;
- BOM supports recursive explosion, Decimal quantities and cycle detection;
- Routing/BOP is separate from BOM and can reference G1 resources;
- manufacturing calendars/effectivity are represented without duplicating APS schedules;
- Prolowin import contract v1.0.0 is implemented through staging/validation;
- complete-report FIN normalization does not double-count operation rows;
- direct hierarchical structure can create candidate BOM revisions;
- canonical recursive explosion reconciles against validated FIN snapshots;
- known five-product corpus is covered without committing proprietary PDFs;
- zero unresolved blocker-level data-quality issue exists in release evidence;
- G0/G1 regression, G2 tests, dependency audits and runtime regression are green;
- explicit release approval is received before merge/release.

## Current status
G2 is **VALIDATED** and awaiting an explicit release decision. PR #8 remains DRAFT; validation does not authorize merge or release.

### G2.1 — Article & UoM foundation
- implementation head: `1f3f4649df1370e22a3b46ce087bd0d68f7627f8`;
- GitHub Actions: `G2 Master Data` run #1;
- result: **SUCCESS**;
- Alembic head: `0006_g2_1`;
- G0 regression: 5 passed;
- G1 regression: 30 passed;
- G2 tests: 6 passed;
- frontend regression: 6 passed + typecheck + production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- runtime regression: passed;
- next slice: **G2.2 — Product configurations**.

### G2.2 — Product configurations
- implementation head: `f2f07b68ea21b475d3fdc4faf87c5306ba76ec54`;
- GitHub Actions: `G2 Master Data` run #6;
- result: **SUCCESS**;
- Alembic head: `0007_g2_2`;
- one ProductConfiguration per exact FINISHED_PRODUCT Article;
- width uses Decimal semantics and requires an active canonical LENGTH UoM;
- G0 regression: 5 passed;
- G1 regression: 30 passed;
- G2 tests: 12 passed with no application deprecation warnings;
- frontend regression: 7 passed + typecheck + production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- runtime regression: passed;
- next slice: **G2.3 — Supplier master**.

### G2.3 — Supplier master
- implementation head: `5e31e6046f5c42a8bbd44729c2077fb090f8a402`;
- GitHub Actions: `G2 Master Data` run #10;
- result: **SUCCESS**;
- Alembic head: `0008_g2_3`;
- canonical Supplier code + legal/trade identity and broad supply category;
- source mappings support multiple systems and REVIEW_REQUIRED records without invented consolidation;
- SupplierArticle carries supplier article code, preferred flag, lead time, MOQ and canonical order UoM;
- G0 regression: 5 passed;
- G1 regression: 30 passed;
- G2 tests: 18 passed;
- frontend regression: 7 passed + typecheck + production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- runtime regression: passed;
- next slice: **G2.4 — BOM**.

### G2.4 — BOM
- implementation head: `864b42ffd9018225d2c26df126a481fbdd30b9af`;
- GitHub Actions: `G2 Master Data` run #16;
- result: **SUCCESS**;
- Alembic head: `0009_g2_4`;
- BOMRevision is attached to an exact ArticleRevision and begins as DRAFT;
- only DRAFT BOMs accept component changes; published structures are immutable;
- controlled publish/supersede lifecycle preserves historical effectivity;
- component quantities use Decimal semantics and preserve raw source UoM;
- recursive explosion multiplies all levels, retains path provenance and aggregates only after path calculation;
- cycle detection blocks recursive loops;
- ambiguous unpinned child revisions are rejected when multiple effective active BOMs exist;
- G0 regression: 5 passed;
- G1 regression: 30 passed;
- G2 tests: 25 passed;
- frontend regression: 7 passed + typecheck + production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- runtime regression: passed;
- next slice: **G2.5 — Routing/BOP**.

### G2.5 — Routing/BOP
- implementation head: `5938a427a8128b99bfd6fc0d06d88fc75adde63f`;
- GitHub Actions: `G2 Master Data` run #22;
- result: **SUCCESS**;
- Alembic head: `0010_g2_5`;
- RoutingRevision is tied to an exact ArticleRevision and begins as DRAFT;
- operations preserve source code/description independently from BOM demand;
- operation kind, schedulability and completion-marker semantics are explicit;
- routing operations reference G1 Area/WorkCenter and ResourceAssignment references G1 Resource;
- work-center/resource hierarchy is validated and no duplicate resource master is introduced;
- nominal rate uses Decimal semantics with an explicit rate UoM;
- only DRAFT routings accept operations/resource assignments;
- controlled publish/supersede lifecycle preserves historical effectivity;
- effective-routing lookup and complete definition projection are available for APS/MES consumers;
- standalone canonical Process identity is intentionally deferred because no governed Process master exists yet;
- G0 regression: 5 passed;
- G1 regression: 30 passed;
- G2 tests: 32 passed;
- frontend regression: 7 passed + typecheck + production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- runtime regression: passed;
- next slice: **G2.6 — Calendars/effectivity**.

### G2.6 — Calendars/effectivity
- implementation head: `647e2af2ceaebe3b14a6f2add17b9e6a475c2339`;
- GitHub Actions: `G2 Master Data` run #32;
- result: **SUCCESS**;
- Alembic head: `0011_g2_6`;
- calendar revisions bind to exactly one G1 Plant, Area, WorkCenter or Resource;
- IANA timezone is explicit and stable across one calendar code's revisions;
- weekly availability is minute-granular, Decimal capacity-safe and supports overnight shifts;
- dated CLOSED / AVAILABLE_OVERRIDE exceptions override recurring windows;
- runtime resolution precedence is Resource > WorkCenter > Area > Plant;
- published calendars are immutable and supersede preserves historical effectivity;
- historical resolution includes SUPERSEDED revisions inside their closed effectivity window;
- the backend runtime image explicitly resolves `America/Argentina/Cordoba`;
- APS receives nominal availability/capacity evidence but remains owner of production scheduling;
- G0 regression: 5 passed;
- G1 regression: 30 passed;
- G2 tests: 39 passed;
- frontend regression: 7 passed + typecheck + production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- runtime regression: passed;
- next slice: **G2.7 — Prolowin assimilation**.

### G2.7 — Prolowin assimilation
- implementation head: `89f040cc8c2310688bdc209e529abe5e23555c60`;
- GitHub Actions: `G2 Master Data` run #41;
- result: **SUCCESS**;
- Alembic head: `0012_g2_7`;
- immutable complete-report and direct-structure staging implemented with PostgreSQL mutation guards;
- complete report FIN rows become flattened requirements and non-FIN rows become SourceOperationState evidence;
- exactly-one-FIN/root guards create BLOCKER DQ issues and prevent canonical application;
- raw Prolowin UoM values are preserved and unresolved aliases enter governed WARNING state;
- Article identity is globally reused by Prolowin code without prefix inference;
- complete flattened reports never author BOM parent-child edges;
- direct parent-child inputs validate reachability, duplicates and cycles before creating DRAFT ArticleRevision/BOMRevision candidates;
- candidate BOMs remain unpublished pending reconciliation/approval;
- candidate recursive explosion is compared against the complete FIN projection using Decimal arithmetic and approved UoM mappings/conversions;
- reconciliation produces MATCH / MATCH_WITH_WARNINGS / MISMATCH / BLOCKED evidence with per-article variance;
- selection of an unrelated BOM is rejected as a request error and does not contaminate source DQ;
- material `14027` is covered by an X-6111 regression trace from FIN quantity 6 through two-level canonical explosion;
- the five authoritative product corpus is represented in the public repository only by non-proprietary derived metadata/counts;
- identical source+parser replay is idempotent and does not duplicate canonical identities;
- G0 regression: 5 passed;
- G1 regression: 30 passed;
- G2 tests: 48 passed;
- frontend regression: 7 passed + typecheck + production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- runtime regression: passed;
- next slice: **G2.8 — Gate hardening**.


### G2.8 — Gate hardening
- hardening implementation head: `3ee6e6b1f83346a3a6a78702ccaa68a9a39913f7`;
- GitHub Actions: `G2 Master Data` push run #51 — **SUCCESS**;
- Alembic: exactly one head, `0012_g2_7`;
- clean PostgreSQL upgrade from base to head: **PASS**;
- SQLAlchemy/Alembic schema drift check: **PASS**;
- full `downgrade base` then `upgrade head` replay: **PASS**;
- G0 regression: **5 passed**;
- G1 regression: **30 passed**;
- G2 regression: **48 passed**;
- frontend: **7 passed** + typecheck + production build;
- repository secret scan and supply-chain pin checks: **PASS**;
- Python dependency audit: **no known vulnerabilities**;
- npm audit: **0 vulnerabilities**;
- released-runtime regression: **PASS**;
- G2 aggregate gate: **PASS**;
- no release action performed.

Hardening exposed one pre-existing metadata drift in G1 IAM index naming. The physical schema was already correct: migrations contained `ix_iam_assignment_user_id` and `ix_iam_assignment_role_id`, while ORM `index=True` generated different expected names. The ORM metadata now declares the persisted index names explicitly; no data migration or schema rewrite was required.

Exit assessment: **VALIDATED**. Release remains governed by ADR-0004 and requires explicit approval before PR merge/release.
