# G2 — Master Data

Status: **IN PROGRESS**  
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
- **G2.5 — Routing/BOP:** routing revisions, operations and references to G1 resources.
- **G2.6 — Calendars/effectivity:** manufacturing calendars and effectivity rules consumed by scheduling.
- **G2.7 — Prolowin assimilation:** immutable staging, FIN normalization, data-quality quarantine and reconciliation.
- **G2.8 — Gate hardening:** regression corpus, import/reconciliation evidence, security and release-facing summary.

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

## Current slice
G2.5 — Routing/BOP.

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
