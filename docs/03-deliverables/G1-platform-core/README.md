# G1 — Platform Core

Status: **IN PROGRESS**  
Started: 2026-10-28  
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
- **G1.4 — Identity/RBAC:** User, Role, Permission, assignment and authorization service boundary.
- **G1.5 — Audit:** append-only audit event baseline for privileged/core actions.
- **G1.6 — Frontend shell:** React/TypeScript/Vite application shell consuming the documented API.
- **G1.7 — Runtime:** Docker Compose DEV/TEST topology and configuration examples without committed secrets.
- **G1.8 — Gate hardening:** tests, evidence, security review and release-facing summary.

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
