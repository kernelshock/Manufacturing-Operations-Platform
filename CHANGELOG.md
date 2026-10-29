# Changelog

All notable changes to the Manufacturing Operations Platform are documented here.

## [Unreleased]

### Added
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
- G1 Platform Core reached VALIDATED on 2026-10-29; PR #6 remains draft pending explicit release approval.
- G0 Architecture Foundation released on 2026-10-28 after explicit approval; PR #1 merged to `main` as `6f79f82155789c02c8138b2caec1f617b46619db`.

### Project baseline
- The FAIC v0.x/v1.x dashboard is treated as a functional reference prototype.
- The new platform begins from v2.0 architecture foundations rather than extending the prototype monolith.
