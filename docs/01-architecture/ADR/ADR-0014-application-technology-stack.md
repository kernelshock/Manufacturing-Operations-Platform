# ADR-0014 — Application Technology Stack

Status: Accepted  
Date: 2026-10-28

## Decision

### Backend
- Python
- FastAPI for HTTP/API boundary
- SQLAlchemy 2.x for persistence mapping
- Alembic for schema migrations
- Pydantic models for API/configuration validation
- pytest for backend and contract tests

### Database
- PostgreSQL as the transactional canonical database.
- A supported major version is pinned by each release manifest; G0 does not bind the project to a specific PostgreSQL major.

### Frontend
- React
- TypeScript
- Vite-based build tooling
- component architecture designed for desktop/tablet browser use on the plant intranet

### API
- REST/JSON for synchronous module and UI contracts
- OpenAPI generated from the application contract
- event-oriented integration through a transactional outbox/domain-event mechanism inside the modular monolith

### Background work
Initial background processing uses application worker processes backed by PostgreSQL-persisted jobs/outbox records.

Redis/message brokers are not mandatory for G1. They may be introduced only when measured throughput/latency requires them.

### APS
The APS module is intentionally isolated behind a solver contract. Python enables later use of optimization libraries such as OR-Tools without coupling the rest of the platform to a solver implementation.

## Rationale
- aligns with the project's data/optimization workload;
- strong Python ecosystem for scheduling, analytics and data import;
- PostgreSQL supports transactional integrity, recursive queries, JSON metadata and mature backup tooling;
- React/TypeScript supports the interactive Gantt, route editor and shop-floor/web UIs;
- avoids premature distributed infrastructure.

## Constraints
- domain logic must not depend directly on FastAPI;
- persistence models must not become domain contracts;
- frontend consumes documented APIs, not database structures;
- solver implementation remains replaceable.

## Deferred
Exact dependency versions are chosen and locked during G1 implementation after compatibility tests.
