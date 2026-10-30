# Changelog

All notable changes to the Manufacturing Operations Platform are documented here.

## [Unreleased]

### Added
- G3.5 governed lifecycle and historical completion with ON_TIME/DELAYED administrative classification, reasoned cancellation and safe DRAFT correction without fabricated MES actuals.
- G3.4 exact G2 RoutingRevision binding with deterministic resolution, ambiguity rejection and explicit audited override provenance.
- G3.3 explicit SIMPLE/DOUBLE_DECK vehicle topology with SINGLE/UPPER/LOWER product allocation and source-document grouping independent from floor inference.
- G3.2 Taquilla product composition with exact G2 finished-product references, Decimal demand quantities, ordering and idempotent source-line identity.
- G3.1 Production Plan and Taquilla foundation with stable operational-demand identity, controlled lifecycle, RBAC, audit and API.
- G2.1 canonical Article/ArticleRevision and Unit-of-Measure foundation with Master Data RBAC/audit/API baseline.
- G2.2 product configuration projection for finished Articles with family/model/class/width metadata and Master Data frontend visibility.
- G2.3 canonical Supplier master with source-system mappings and Article sourcing/lead-time/MOQ relationships.
- G2.4 revisioned BOM with immutable published structures, Decimal-safe recursive explosion, path provenance, effectivity and cycle detection.
- G2.5 revisioned Routing/BOP with operation semantics, effectivity and assignments to G1 Area/WorkCenter/Resource identities.
- G2.6 versioned manufacturing calendars with hierarchical target resolution, weekly availability, dated exceptions and nominal capacity factors.
- G2.7 Prolowin assimilation with immutable staging, FIN normalization, direct-hierarchy BOM candidates, DQ quarantine and recursive reconciliation evidence.
- G2.8 gate hardening with Alembic head uniqueness, model/schema drift detection, full migration rollback/replay and release-facing validation evidence.
- G1 Platform Core executable backend, PostgreSQL/Alembic persistence, organizational hierarchy and local scoped RBAC.
- Local session authentication with Argon2 password hashing and server-side opaque sessions.
- Append-only PostgreSQL audit trail for authentication, IAM administration and privileged core mutations.
- React/TypeScript/Vite frontend shell with session login, RBAC-driven navigation, operational context and system status surfaces.
- Reproducible Docker Compose DEV/TEST runtime with PostgreSQL 18, Alembic migration gate, FastAPI, nginx frontend boundary and end-to-end smoke validation.
- G1 gate hardening with persistent login lockout, nginx rate limiting/security headers, secret scanning, vulnerability audits, pinned Actions/container images and enforced dependency lockfiles.
- Prolowin manufacturing-definition import contract and JSON Schema.
- Five-product Prolowin reference-corpus analysis and reconciliation rules.
- Recursive BOM/ABM and separate BOP/Routing canonical model.
- FAIC e-Kanban/replenishment-loop baseline and prospective PP/PR recalibration model.
- Reference deployment topology, authentication/RBAC, backup/restore and multi-plant architecture decisions.
- Public-repository data boundary for proprietary FAIC evidence.
- G0 Architecture Foundation repository structure.
- Governance model with stage gates and release criteria.
- Versioned roadmap and worklog templates.
- Architecture Decision Record (ADR) framework.
- Initial event catalog and canonical-domain documentation.
- Automated G0 repository structure check.

### Changed
- G2 Master Data released on 2026-10-29 after explicit approval; PR #8 merged to `main` as `e476edb8f1862613ff90f2a22a514d3f53a05ec5`.
- G1 Platform Core released on 2026-10-29 after explicit approval; PR #6 merged to `main` as `3412a9b3f78303166f81e22e32a7b167ad2dc19e`.
- G0 Architecture Foundation released on 2026-10-28 after explicit approval; PR #1 merged to `main` as `6f79f82155789c02c8138b2caec1f617b46619db`.

### Project baseline
- The FAIC v0.x/v1.x dashboard is treated as a functional reference prototype.
- The new platform begins from v2.0 architecture foundations rather than extending the prototype monolith.
