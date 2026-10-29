# Infrastructure

Deployment and runtime infrastructure assets live here.

Implemented G1.7 areas:
- `docker/` — backend/frontend images and nginx reverse-proxy configuration;
- `compose/` — parameterized DEV/TEST single-host topology;
- `config/` — non-secret runtime environment examples;
- `scripts/` — start, stop, bootstrap and smoke-test helpers;
- `deployment/` — reference topology documentation.

Target baseline: Linux intranet deployment, PostgreSQL, web frontend and FastAPI modular-monolith backend. The reference topology is defined in `deployment/FAIC-REFERENCE-TOPOLOGY.md`; exact FAIC host sizing is validated before pilot.

The background-worker process described by ADR-0015 remains intentionally absent until its durable job/outbox contract is implemented. G1.7 does not introduce a placeholder worker.
