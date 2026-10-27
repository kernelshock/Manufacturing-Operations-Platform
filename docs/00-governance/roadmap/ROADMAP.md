# Manufacturing Operations Platform — Roadmap

Last updated: 2026-10-27  
Baseline: G0 Architecture Foundation

## Objective
Deliver a modular, configurable Manufacturing Operations Management platform that can be introduced progressively at FAIC without abrupt changes to current operating logic, while remaining reusable for other industrial structures.

## Gate roadmap

| Gate | Scope | Demonstrable outcome | Status |
|---|---|---|---|
| G0 | Architecture Foundation | Architecture, governance, canonical model, events, roadmap and release rules approved | IN PROGRESS |
| G1 | Platform Core | Organization/plant model, identity, roles, configuration, audit and core API running | PLANNED |
| G2 | Master Data | Products, variants, materials, suppliers, resources, calendars and importers | PLANNED |
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


## G0 progress snapshot — 2026-10-27
Confirmed:
- repository governance baseline;
- modular-monolith / API-first / event-oriented architecture direction;
- FAIC v1.x frozen as functional reference;
- Prolowin role: purchasing reference, purchase orders, supplier/material reference and supplier-delay follow-up;
- Prolowin practical integration: controlled CSV/XLSX exports, daily or weekly;
- Tango role: formal remittances, invoices, payments and accounting chain, outside current scope;
- local G0 structural tests: 2 passed.

Open:
- authoritative operational stock source/ledger;
- application technology stack;
- FAIC deployment topology;
- authentication/identity source;
- backup/restore requirements;
- multi-plant/multi-tenant isolation strategy;
- Prolowin API availability (non-blocking research item).
