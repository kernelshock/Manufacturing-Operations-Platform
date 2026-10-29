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
- **G2.1 — Article & UoM foundation:** Article, ArticleRevision, UoM, UoM aliases, RBAC, audit and API.
- **G2.2 — Product configurations:** commercial/manufacturing configuration metadata tied to exact Article identity.
- **G2.3 — Supplier master:** supplier identity and source mappings required by purchasing/material flows.
- **G2.4 — BOM:** revisioned BOM and recursive component relations with Decimal-safe quantities and cycle detection.
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
G2.1 — Article & UoM foundation.
