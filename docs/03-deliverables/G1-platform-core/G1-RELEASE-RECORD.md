# G1 Release Record — Platform Core

Date: 2026-10-29  
Gate: G1 — Platform Core  
Status: **RELEASED**

## Approval
Explicit project-direction approval was received:

> Autorizo la liberación de G1

This approval satisfied the human release gate defined by G1 governance.

## Validated baseline
- final validated branch head: `57f5b154e4a07e463ebe6ec7efb53cf45980e690`;
- canonical hardening implementation evidence: `127f894aad161f152878c6212df06fc3523547ef`;
- Alembic head: `0005_g1_8`.

Final validation on the release head:
- G1 Platform Core push run #93: **SUCCESS**;
- G1 Platform Core PR run #94: **SUCCESS**;
- G0 Architecture Structure PR run #77: **SUCCESS**.

Validated results:
- G0 regression: 5 passed;
- G1 backend: 30 passed;
- frontend: 6 passed plus typecheck and production build;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- repository secret scan: passed;
- supply-chain pin check: passed;
- full Docker Compose runtime smoke: passed.

## Merge
- release PR: #6 — `G1: Platform Core`;
- PR state before approval: draft;
- approval recorded on PR;
- PR marked ready after approval;
- merge method: merge commit;
- release merge commit: `3412a9b3f78303166f81e22e32a7b167ad2dc19e`;
- target branch: `main`.

## Released capability
G1 establishes the executable platform foundation for G2+:
- FastAPI REST/OpenAPI backend;
- PostgreSQL 18 + SQLAlchemy + Alembic persistence;
- Organization → Plant → Area → WorkCenter → Resource hierarchy;
- application-local identity and scoped RBAC;
- Argon2 password hashing and opaque server-side sessions;
- persistent login lockout and reverse-proxy rate limiting;
- append-only audit;
- React/TypeScript/Vite frontend shell;
- Docker Compose DEV/TEST runtime;
- pinned Actions/container bases and enforced Python/npm dependency locks;
- automated security, regression and end-to-end gates.

## Deferred obligations
Release of G1 does not waive later-stage requirements:
- production HTTPS/ingress under ADR-0015;
- automated separated backup and successful restore evidence under ADR-0017 before Parallel/Production;
- OIDC federation when enterprise identity is introduced;
- durable background worker/outbox execution when that contract is introduced;
- business-module and FAIC operational validation in later gates.

## Disposition
G1 — Platform Core is **RELEASED** and may be used as the governed baseline for G2 — Master Data.
