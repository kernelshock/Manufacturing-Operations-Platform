# G2 Gate Review — Master Data

Date: 2026-10-29  
Gate: G2 — Master Data  
Decision: **VALIDATED — RELEASE APPROVAL PENDING**

## Scope reviewed
G2.1 through G2.8:
- Article & UoM foundation;
- Product Configurations;
- Supplier Master;
- revisioned BOM;
- Routing/BOP;
- manufacturing calendars/effectivity;
- Prolowin assimilation;
- gate hardening.

## Acceptance decision
The gate satisfies its technical validation criteria:
- canonical identities are persisted and audited;
- manufacturing definitions are revisioned rather than silently overwritten;
- Decimal semantics are maintained for manufacturing quantities;
- raw source UoM is preserved and mappings are governed;
- BOM recursion, effectivity and cycle detection are implemented;
- Routing/BOP remains distinct from BOM demand;
- G1 resource identities are reused rather than duplicated;
- nominal calendars do not absorb APS scheduling responsibility;
- Prolowin complete reports normalize FIN without double-counting operation rows;
- only hierarchy-preserving direct structures may author candidate BOM edges;
- reconciliation compares recursive candidate demand against validated FIN projections;
- the five-product reference corpus is represented without publishing proprietary source PDFs;
- blocker DQ prevents canonical application;
- migrations are clean, single-headed, reversible and synchronized with ORM metadata;
- G0/G1/G2/frontend/security/dependency/runtime gates are green.

## Hardening finding
G2.8 detected a pre-existing IAM index-name metadata mismatch.

Risk before remediation:
ORM metadata and migration history disagreed about the names of two existing indexes, which would have caused future autogeneration noise and could mask genuine schema drift.

Resolution:
ORM metadata was aligned to the persisted migration names. No database rewrite was necessary.

Residual risk: **LOW / ACCEPTED FOR VALIDATION**.

## Known deliberate deferrals
These are not G2 blockers:
- standalone canonical Process master remains deferred;
- APS finite-capacity scheduling is not implemented in Master Data;
- MES execution is not implemented in Master Data;
- purchasing transactions, receiving and supplier evaluation remain outside Supplier Master;
- unmapped source UoM and unknown source classifications remain visible governance states rather than inferred values.

## Evidence
Canonical hardening validation:
- branch head: `3ee6e6b1f83346a3a6a78702ccaa68a9a39913f7`;
- G2 Master Data push run #51: **SUCCESS**;
- Alembic head: `0012_g2_7`;
- migration single-head check: **PASS**;
- clean migration: **PASS**;
- `alembic check`: **PASS**;
- downgrade base → upgrade head replay: **PASS**;
- G0: **5 passed**;
- G1: **30 passed**;
- G2: **48 passed**;
- frontend: **7 passed**, typecheck/build PASS;
- Python audit: **PASS**;
- npm audit: **PASS**;
- runtime regression: **PASS**;
- aggregate G2 gate: **PASS**.

## Governance decision
G2 may transition from **IN PROGRESS** to **VALIDATED**.

G2 may **not** transition to RELEASED yet.

PR #8 remains DRAFT. Merge/release requires an explicit release decision under ADR-0004.
