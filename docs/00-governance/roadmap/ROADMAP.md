# Manufacturing Operations Platform — Roadmap

Last updated: 2026-10-29  
Baseline: G0 Architecture Foundation

## Objective
Deliver a modular, configurable Manufacturing Operations Management platform that can be introduced progressively at FAIC without abrupt changes to current operating logic, while remaining reusable for other industrial structures.

## Gate roadmap

| Gate | Scope | Demonstrable outcome | Status |
|---|---|---|---|
| G0 | Architecture Foundation | Architecture, governance, canonical model, events, roadmap and release rules approved | RELEASED |
| G1 | Platform Core | Organization/plant model, identity, roles, configuration, audit and core API running | RELEASED |
| G2 | Master Data | Products, variants, materials, suppliers, resources, calendars and importers | IN PROGRESS |
| G3 | Demand / Plan / Taquilla / Routing | Plans, taquillas, products and configurable routing operational | PLANNED |
| G4 | APS | Finite-capacity scheduling, Gantt, constraints, priorities and what-if | PLANNED |
| G5 | MES | Shop-floor execution, start/finish, quantities, scrap, transfer and traceability | PLANNED |
| G6 | Materials | ABM/BOM, theoretical demand, actual consumption, inventory and reconciliation | PLANNED |
| G7 | Kanban + Purchasing | PP/PR, replenishment signals, supplier lead time, purchasing and receipts | PLANNED |
| G8 | Maintenance | Assets, work orders, downtime and production-capacity impact | PLANNED |
| G9 | Workforce | Shifts, skills, availability, assignment and productive hours | PLANNED |
| G10 | Intelligence / RPD | Module KPI, targets, cross-module executive reporting and actions | PLANNED |
| G11 | Integration Hub | ERP/files/API adapters with explicit system-of-record contracts | PLANNED |
| G12 | Industrial Pilot | Controlled pilot using real FAIC data in shadow/parallel mode | PLANNED |
| G13 | FAIC Production Release | Validated production deployment | PLANNED |
| G14 | Multi-industry Package | Installable/configurable distribution for other factories | PLANNED |

## Preliminary timeline
This is a planning baseline, not a commitment. It must be recalibrated after G0.

| Phase | Indicative duration |
|---|---:|
| G0 Architecture Foundation | 2 weeks |
| G1 Core | 4 weeks |
| G2 Master Data | 4 weeks |
| G3 Orders / Routing | 4 weeks |
| G4 APS | 6 weeks |
| G5 MES | 5 weeks |
| G6 Materials | 4 weeks |
| G7 Purchasing / Kanban | 3 weeks |
| G8 Maintenance | 3 weeks |
| G9 Workforce | 3 weeks |
| G10 Intelligence / RPD | 4 weeks |
| G11 Integrations | progressive / parallel |
| G12–G13 Pilot and release | 6+ weeks |

Several later gates may overlap once Core contracts are stable.

## Release principle
A gate is RELEASED only when:
- scope and acceptance criteria exist;
- required ADRs are resolved;
- tests pass;
- evidence is stored;
- user/direction-facing deliverable exists;
- open critical risks are accepted or resolved;
- roadmap and changelog are updated.

## Adoption maturity
Every operational module should progress through:

`OBSERVE → REPLICATE → RECOMMEND → CONTROL → AUTOMATE`

and deployment through:

`DEVELOPMENT → SIMULATION → SHADOW MODE → PARALLEL → VALIDATION → PRODUCTION`.


## G0 progress snapshot — 2026-10-28
Confirmed:
- repository governance baseline;
- modular-monolith / API-first / event-oriented architecture direction;
- FAIC v1.x frozen as functional reference;
- Prolowin role: purchasing reference, purchase orders, supplier/material reference and supplier-delay follow-up;
- Prolowin practical integration: controlled CSV/XLSX exports, daily or weekly;
- Tango role: formal remittances, invoices, payments and accounting chain, outside current scope;
- physical point-of-use Kanban container/card state confirmed as the initial operational material truth;
- material replenishment is continuous visual review, not a periodic stock review;
- G0 automated validation suite: 5 passed; release-gate evidence GitHub Actions run #72;
- legacy PP/PR and supplier-performance data classified as non-verifiable;
- prospective measurement baseline required before recalibration;
- five-product authoritative Prolowin PDF corpus analyzed;
- recursive BOM and separate BOP/Routing model validated across Enterprise, Moonraker, Apollo and Discovery examples;
- Master Data established as canonical manufacturing-definition owner;
- relational physical schema baseline defined for Article/BOM/Routing/staging/data quality/reconciliation;
- Prolowin import contract v1.0.0 + machine-readable JSON Schema defined;
- bulk-assimilation acceptance criteria defined.

Resolved/deferred for G0:
- exact-stock maturity: deferred to G6/G7; physical/e-Kanban remains initial operational truth;
- application stack: accepted in ADR-0014;
- deployment topology: accepted in ADR-0015;
- authentication/RBAC: accepted in ADR-0016;
- backup/restore: accepted in ADR-0017;
- multi-plant/tenant strategy: accepted in ADR-0018;
- Prolowin API availability: deferred to G11 as non-blocking research.

## G0 release record — 2026-10-28
- explicit release approval recorded;
- PR #1 merged into `main`;
- validated head: `807fc323c5e00b361ffca475d28b10fbb028e3ae`;
- release merge commit: `6f79f82155789c02c8138b2caec1f617b46619db`;
- GitHub Actions `G0 Architecture Structure` run #72: SUCCESS;
- G0 status: **RELEASED**.

## G1 start record — 2026-10-28
- branch: `feat/G1-platform-core`;
- base: released `main` commit `4ca6a279ba661a813598c745befd9639435c2e8f`;
- implementation must conform to ADR-0014 through ADR-0018;
- G1 status: **IN PROGRESS**.

## G1 validation record — 2026-10-29
- branch: `feat/G1-platform-core`;
- base: released G0/main commit `4ca6a279ba661a813598c745befd9639435c2e8f`;
- validated implementation head: `127f894aad161f152878c6212df06fc3523547ef`;
- GitHub Actions `G1 Platform Core` run #91: **SUCCESS**;
- Alembic head: `0005_g1_8`;
- G0 regression: 5 passed;
- G1 backend: 30 passed;
- frontend: 6 tests + typecheck + production build passed;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- full Docker Compose runtime smoke: passed;
- PR #6 opened as **DRAFT**;
- G1 status: **VALIDATED — awaiting explicit release approval**;
- no merge/release is authorized by validation alone.

## G1 release record — 2026-10-29
- explicit release approval received: **"Autorizo la liberación de G1"**;
- final validated branch head: `57f5b154e4a07e463ebe6ec7efb53cf45980e690`;
- G1 Platform Core push run #93: **SUCCESS**;
- G1 Platform Core PR run #94: **SUCCESS**;
- G0 Architecture Structure PR run #77: **SUCCESS**;
- PR #6 marked ready and merged into `main`;
- release merge commit: `3412a9b3f78303166f81e22e32a7b167ad2dc19e`;
- G1 status: **RELEASED**.

## G2 start record — 2026-10-29
- branch: `feat/G2-master-data`;
- base: released G1/main commit `ac8e27f7596fda999f17253a646c06386ed1cfae`;
- implementation follows the G0 Master Data/BOM/BOP schema and Prolowin import contract;
- G2.1 starts with Article/ArticleRevision and UoM/UoMAlias as the prerequisite canonical identities;
- G2 status: **IN PROGRESS**.
