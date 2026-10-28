# ADR-0001 — Modular Monolith as Initial Runtime Architecture

Status: Accepted  
Date: 2026-10-27

## Context
The platform must integrate planning, execution, materials, purchasing, maintenance, workforce and intelligence while remaining deployable on industrial intranet infrastructure and configurable for different factories.

Premature microservices would add deployment, observability, transactional and operational complexity before module boundaries are validated in production.

## Decision
Use a modular monolith for the initial runtime, with strict internal module boundaries, explicit contracts and separate persistence ownership by domain.

The architecture must preserve the option to extract modules into independent services later without changing domain semantics.

## Consequences
Positive:
- simpler deployment and backup;
- lower operational overhead;
- easier local/intranet installation;
- faster iteration during domain discovery;
- transactional consistency where needed.

Constraints:
- module boundaries must be enforced in code;
- no cross-module table access by convenience;
- integration must use APIs/domain services/events rather than hidden coupling.
