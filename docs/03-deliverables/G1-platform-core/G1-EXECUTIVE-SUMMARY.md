# G1 Executive Summary — Platform Core

Date: 2026-10-29  
Audience: Direction / project governance  
Status: **RELEASED**

## What G1 delivers
G1 turns the G0 architecture into a working platform foundation.

MOP now has:
- a running backend/API;
- PostgreSQL persistence with controlled migrations;
- the Organization → Plant → Area → WorkCenter → Resource hierarchy;
- individual users, roles and scoped permissions;
- server-side sessions and authorization;
- immutable audit history;
- a React operator shell;
- a reproducible container runtime;
- automated security, dependency and end-to-end validation.

## Why this matters
Later modules such as Master Data, Demand/Taquilla, APS, MES, Materials, Kanban/Purchasing, Maintenance and Workforce can now be added onto one governed platform instead of creating isolated applications or duplicating identity, database, audit and deployment logic.

## Controls established
The baseline now includes:
- Argon2 password protection;
- persistent login lockout and reverse-proxy rate limiting;
- scoped RBAC enforced by the server;
- append-only audit;
- secret scanning;
- vulnerability scanning;
- pinned build/runtime supply-chain components;
- dependency lockfiles;
- database-aware readiness;
- clean-database migration tests;
- full-stack runtime smoke tests.

## Validation result
Canonical G1 hardening run #91 passed:
- 5 G0 regression tests;
- 30 G1 backend tests;
- 6 frontend tests plus typecheck/build;
- Python audit with no known vulnerabilities;
- npm audit with 0 vulnerabilities;
- complete Docker Compose smoke flow through the public runtime boundary.

## What G1 does not claim
G1 is a DEV/TEST Platform Core baseline, not the FAIC production release.

Before later production stages, separate gates still have to address:
- production TLS/network deployment;
- automated backup/restore and recovery evidence;
- business-module validation with FAIC data;
- operational pilot/shadow/parallel evidence.

## Release decision
Explicit release approval was received on 2026-10-29. PR #6 was merged to `main`; G1 — Platform Core is **RELEASED**. This does not change the later production-stage obligations listed above.
