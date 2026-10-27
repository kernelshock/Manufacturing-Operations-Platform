# ADR-0003 — FAIC v1.x as Functional Reference

Status: Accepted  
Date: 2026-10-27

## Context
The FAIC dashboard/APS prototypes v0.x–v1.4 accumulated valuable domain learning but are implemented as a large browser application with local persistence.

## Decision
Freeze the latest v1.x implementation as a Functional Reference Implementation.

It is a source of:
- workflows;
- terminology;
- edge cases;
- user-interface learning;
- parsers;
- scheduling rules;
- production routes;
- reporting requirements.

It is not the production code foundation for v2.x.

## Consequences
New functionality is specified from validated behavior, then reimplemented on the new architecture. Direct feature accumulation on the old monolith stops except for critical reference fixes.
