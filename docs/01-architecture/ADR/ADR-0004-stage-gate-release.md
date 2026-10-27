# ADR-0004 — Stage-gate Validation and Release

Status: Accepted  
Date: 2026-10-27

## Decision
Every project gate uses the lifecycle:

PLANNED → IN PROGRESS → VALIDATED → RELEASED

BLOCKED may be used when a dependency prevents progress.

A gate may not be VALIDATED without:
- acceptance criteria;
- tests;
- evidence;
- resolved/accepted critical risks;
- documented decisions.

A gate may not be RELEASED without an explicit release decision and updated roadmap/changelog.

## Rationale
The platform will affect production, stock, purchasing and maintenance decisions. Feature completion alone is insufficient; traceable validation is required.
