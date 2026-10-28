# G0 Architecture Foundation — Executive Summary

## Project transition
The FAIC v0.x/v1.x dashboard cycle is frozen as a functional discovery/reference phase. The new program is a modular Manufacturing Operations Management platform.

## Architecture baseline
- modular monolith initially;
- API-first contracts;
- event-oriented cross-module integration;
- versioned configuration;
- auditable deterministic transactional rules;
- future extractability into services;
- progressive industrial adoption.

## Initial modules
Core, Master Data, Demand/Orders, APS, MES, Materials, Purchasing, Maintenance, Workforce and Intelligence.

## Migration principle
Reflect reality → measure → understand → improve → automate.

Operational deployment progresses:
Development → Simulation → Shadow Mode → Parallel → Validation → Production.

## G0 architecture decisions resolved
- Operational material truth: physical/e-Kanban state initially; exact perpetual inventory deferred to Materials/Kanban maturity.
- Technology stack: Python/FastAPI + PostgreSQL + React/TypeScript.
- Deployment: on-premise/intranet Linux host or VM using containerized services and browser clients.
- Authentication: application-local identity + RBAC initially, with OIDC federation boundary.
- Backup/recovery: automated PostgreSQL backups with tested restore and production RPO/RTO targets.
- Isolation: single-tenant deployment with multi-plant canonical model.
- Prolowin API verification: deferred/non-blocking; controlled files remain the accepted initial adapter.

## G0 release condition
G0 remains IN PROGRESS until these decisions are resolved or formally deferred and the architecture package is reviewed.


## Confirmed external-system boundary
- **Prolowin:** purchasing reference, purchase orders, supplier/material reference and supplier-delay follow-up; batch exports can be daily or weekly.
- **Tango:** remittances, invoices, payments and accounting chain; explicitly outside the current project phase.
- **Operational material availability:** physical point-of-use Kanban/e-Kanban state is the initial truth; exact perpetual stock is a later maturity step.
