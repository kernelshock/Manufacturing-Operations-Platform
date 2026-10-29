# G1 — Platform Core

Status: **VALIDATED — AWAITING RELEASE APPROVAL**  
Started: 2026-10-28  
Validated: 2026-10-29  
Branch: `feat/G1-platform-core`  
Base release: G0 commit `4ca6a279ba661a813598c745befd9639435c2e8f`

## Purpose
Implement the minimum executable platform foundation required by all later MOP gates without introducing FAIC-specific module forks or prematurely implementing G2+ business functionality.

## Governing decisions
G1 must conform to:
- ADR-0014 — Python + FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL; React + TypeScript + Vite;
- ADR-0015 — containerized Linux deployment, Docker Compose, intranet-first HTTPS topology;
- ADR-0016 — application-local identity, secure session authentication, RBAC and future OIDC boundary;
- ADR-0017 — backup/restore requirements carried into deployment design;
- ADR-0018 — single-tenant runtime with multi-plant domain model.

## G1 scope
1. Repository/application skeleton for backend, frontend and deployment assets.
2. Typed configuration model with secrets outside source control.
3. PostgreSQL persistence baseline and Alembic migration framework.
4. Core organization hierarchy:
   `Organization -> Plant -> Area -> WorkCenter -> Resource`.
5. Local identity:
   users, roles, permissions and scoped authorization foundations.
6. Audit trail for authentication and privileged/core mutations.
7. API baseline:
   versioned REST boundary, OpenAPI, consistent error contract and health endpoints.
8. Containerized DEV/TEST runtime.
9. Automated G1 tests and CI evidence.

## Implementation slices
- **G1.1 — Executable skeleton — COMPLETED:** backend package, FastAPI application factory, typed configuration, versioned API metadata, liveness/readiness endpoints, packaging manifest and CI baseline.
- **G1.2 — Persistence — COMPLETED:** PostgreSQL 18 connection, SQLAlchemy base/session lifecycle, Alembic baseline, database-aware readiness and clean-database CI migration.
- **G1.3 — Organization model — COMPLETED:** Organization, Plant, Area, WorkCenter and Resource persisted through contextual business-code constraints and versioned REST APIs.
- **G1.4 — Identity/RBAC — COMPLETED:** local users, Argon2 password hashing, opaque server-side sessions, roles, seeded permissions, scoped assignments and server-side authorization.
- **G1.5 — Audit — COMPLETED:** PostgreSQL-enforced append-only audit events for authentication, IAM administration and privileged/core mutations, with read-only RBAC-protected query API.
- **G1.6 — Frontend shell — COMPLETED:** React/TypeScript/Vite browser shell with secure login, session bootstrap, permission-driven navigation, organization/plant context, backend readiness, audit view and CI build/test gate.
- **G1.7 — Runtime — COMPLETED:** Docker Compose DEV/TEST topology with PostgreSQL 18, one-shot Alembic migration gate, FastAPI, nginx/React public boundary, secret-safe database configuration, admin bootstrap and end-to-end runtime smoke test.
- **G1.8 — Gate hardening — COMPLETED:** authentication hardening, dependency/security audits, immutable supply-chain pins, reproducible dependency locks, security headers/rate limiting, final evidence and release-facing gate package.

## Exit criteria
G1 can move to **VALIDATED** only when:
- backend and frontend start from documented commands;
- PostgreSQL schema can be created from migrations on a clean database;
- core organization hierarchy is persisted and accessible through tested APIs;
- local users/roles/permissions work with server-side authorization;
- privileged/core changes produce audit records;
- health/readiness endpoints reflect application/database status;
- DEV/TEST container runtime is reproducible;
- secrets are excluded from Git;
- automated G1 tests pass in CI;
- G1 evidence and direction-facing summary exist;
- no critical unresolved G1 risk remains without explicit deferral.

G1 becomes **RELEASED** only after explicit approval.

## Slice evidence
### G1.1 — Executable skeleton
- implementation head: `d3a0daf076423f3c0c334d198d3936d735f2169f`;
- GitHub Actions: `G1 Platform Core` run #1;
- result: **SUCCESS**;
- checks: package installation, compile, G0 regression and G1 tests;
- next slice: **G1.2 — Persistence**.

### G1.2 — Persistence
- implementation head: `57ed637e81e6cb40acfa8d423bde7b943ffbdde3`;
- GitHub Actions: `G1 Platform Core` run #25;
- result: **SUCCESS**;
- PostgreSQL service: 18.x (CI observed 18.6);
- Alembic head: `0001_g1_2`;
- G0 regression: 5 passed;
- G1 suite: 11 passed;
- next slice: **G1.3 — Organization model**.

### G1.3 — Organization model
- implementation head: `6f5fa9b5f9f15c0b300ecc9cdae27b942ea5840d`;
- GitHub Actions: `G1 Platform Core` run #41;
- result: **SUCCESS**;
- Alembic head: `0002_g1_3`;
- hierarchy: Organization → Plant → Area → WorkCenter → Resource;
- G0 regression: 5 passed;
- G1 suite: 16 passed;
- next slice: **G1.4 — Identity/RBAC**.

### G1.4 — Identity/RBAC
- implementation head: `d2cddfb50b52fd714db7e5eee44e59889d3575ad`;
- GitHub Actions: `G1 Platform Core` run #71;
- result: **SUCCESS**;
- Alembic head: `0003_g1_4`;
- password storage: Argon2 via `pwdlib[argon2]`;
- authentication: opaque server-side session + HttpOnly / SameSite=Strict cookie;
- RBAC scopes: global, organization, plant, area;
- G0 regression: 5 passed;
- G1 suite: 21 passed;
- next slice: **G1.5 — Audit**.

### G1.5 — Audit
- implementation head: `9687ce62d3b55739ecfe4f66df251927e1790ac2`;
- GitHub Actions: `G1 Platform Core` run #78;
- result: **SUCCESS**;
- Alembic head: `0004_g1_5`;
- append-only enforcement: PostgreSQL trigger rejects UPDATE and DELETE;
- audit query permission: `audit.read`;
- covered baselines: authentication, IAM administration, organizational core mutations;
- G0 regression: 5 passed;
- G1 suite: 24 passed;
- next slice: **G1.6 — Frontend shell**.

### G1.6 — Frontend shell
- implementation head: `acf5ecfff66088482683eb6114ed32b5a24a70b2`;
- GitHub Actions: `G1 Platform Core` run #81;
- result: **SUCCESS**;
- Node.js CI: 26.13.0 LTS;
- React: 19.3.1;
- Vite: 8.3.5;
- TypeScript: 7.0.2;
- frontend typecheck: passed;
- frontend tests: 6 passed;
- production build: passed;
- backend regression: G0 5 passed / G1 24 passed;
- next slice: **G1.7 — Runtime**.

### G1.7 — Runtime
- implementation head: `aedff6e3e0889046622bf5d834d615ab12b3897d`;
- GitHub Actions: `G1 Platform Core` run #85;
- result: **SUCCESS**;
- Docker Compose observed in CI: v5.1.3;
- PostgreSQL: 18 with persistent volume mounted at `/var/lib/postgresql`;
- migrations: one-shot Alembic service blocks API start until schema is current;
- published boundary: frontend/reverse-proxy only;
- runtime smoke: clean DB → migrations → API ready → UI → admin bootstrap → login → /auth/me → audit;
- backend regression: G0 5 passed / G1 26 passed;
- frontend: typecheck passed / 6 tests passed / production build passed;
- next slice: **G1.8 — Gate hardening**.

### G1.8 — Gate hardening
- validated implementation head: `127f894aad161f152878c6212df06fc3523547ef`;
- GitHub Actions: `G1 Platform Core` run #91;
- result: **SUCCESS**;
- Alembic head: `0005_g1_8`;
- repository secret baseline: passed;
- supply-chain pin baseline: passed;
- Python dependency audit: no known vulnerabilities;
- npm audit: 0 vulnerabilities;
- G0 regression: 5 passed;
- G1 backend: 30 passed;
- frontend: typecheck passed / 6 tests passed / production build passed;
- runtime smoke: passed, including security headers, no-store responses, admin bootstrap, login/session/audit and login-rate-limit verification;
- dependency resolution: Python production/dev locks and npm package lock committed and enforced;
- PR: #6, intentionally **DRAFT**;
- gate status: **VALIDATED — awaiting explicit release approval**.

## Gate disposition
All G1 exit criteria are satisfied for the DEV/TEST Platform Core baseline. G1 is not released by this validation alone.

Explicitly deferred, non-G1 blockers:
- production HTTPS/certificate and plant-network exposure configuration: required by ADR-0015 before production deployment;
- operational backup automation, separated backup storage and restore-test evidence: required by ADR-0017 before Parallel/Production;
- durable background worker/outbox execution process: introduced when the persistent worker contract exists;
- OIDC enterprise federation: preserved behind the authentication boundary for a later gate.

Release action remains a human gate. PR #6 must remain draft until explicit approval.
