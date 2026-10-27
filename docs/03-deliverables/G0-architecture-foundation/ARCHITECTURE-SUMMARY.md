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

## G0 unresolved decisions
1. System of record and access mechanism for articles, stock, suppliers, purchases and receipts.
2. Backend/frontend technology stack.
3. FAIC server/network deployment topology.
4. Authentication/identity source.
5. Database backup/restore and retention requirements.
6. Required multi-plant / multi-tenant isolation level for the first product release.

## G0 release condition
G0 remains IN PROGRESS until these decisions are resolved or formally deferred and the architecture package is reviewed.
