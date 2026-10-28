# core

Status: in progress (G1).

This directory is reserved for the **core** bounded module of the Manufacturing Operations Platform.

G1 implements the approved G0 core contracts. Domain logic remains independent of FastAPI and persistence models, with PostgreSQL, local identity/RBAC, audit and configuration introduced behind explicit module boundaries.
