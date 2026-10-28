# core

Status: in progress (G1).

This directory is reserved for the **core** bounded module of the Manufacturing Operations Platform.

G1 implements the approved G0 core contracts. Domain logic remains independent of FastAPI and persistence models, with PostgreSQL, local identity/RBAC, audit and configuration introduced behind explicit module boundaries.

## Implemented in G1.3
The organizational hierarchy is now executable and persistent:

`Organization -> Plant -> Area -> WorkCenter -> Resource`

Internal UUIDs are immutable identifiers. Business codes remain explicit fields, with uniqueness scoped to the owning parent where applicable. HTTP contracts are exposed under `/api/v1/core`; authorization is intentionally introduced in G1.4 rather than embedded into domain services.
