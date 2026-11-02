# G4 — APS

Status: **IN PROGRESS**  
Started: 2026-11-02  
Base: released G3 main `73b42138d5af14c9f7a6830d0a70ea60eba65200`

## Objective

Transform released G3 demand into an auditable finite-capacity production schedule while preserving strict ownership boundaries between planning and execution.

G4 introduces canonical planning identities and workflows for:
- schedule scenarios and planning runs;
- expansion of G3 Taquilla product demand through exact G2 RoutingRevision operations;
- finite-capacity loading against released G1 resources and G2 manufacturing calendars;
- planned operation sequence and planned start/finish timestamps;
- governed priority, rescheduling and publication;
- operational Gantt projection;
- what-if scenarios that never mutate the published baseline unless explicitly applied.

## Inputs owned by previous gates

G4 consumes, but does not duplicate:
- G1 Organization / Plant / Area / WorkCenter / Resource identities;
- G2 Article, RoutingRevision, RoutingOperation, assignments and manufacturing calendars;
- G3 ProductionPlan, Taquilla, product composition, explicit deck topology and routing bindings.

## Ownership boundaries

### G4 owns
- planning scenario identity and lifecycle;
- planning horizon and solver input snapshot;
- expanded planning operations derived from exact G3 demand + G2 routing;
- planned resource assignment;
- finite-capacity sequence;
- planned start / planned finish;
- schedule conflicts and planning diagnostics;
- schedule publication and supersession;
- Gantt / planning projection;
- what-if scenario state and comparison.

### G4 does not own
- product, BOM, routing or calendar definitions — G2;
- demand identity, requested quantity, Taquilla topology or routing selection — G3;
- actual shop-floor start/finish, produced quantity, scrap or operator execution — G5 MES;
- authoritative inventory/material consumption — G6;
- authoritative purchasing/replenishment — G7;
- authoritative maintenance downtime — G8;
- authoritative workforce availability/skills — G9.

Until later gates are released, G4 must not fabricate material, maintenance or workforce constraints. It may expose explicit extension points and mark those dimensions as unavailable/not evaluated.

## Non-negotiable rules

1. A published schedule is derived evidence; it never mutates G2 routing definitions or G3 demand.
2. Every planned operation retains provenance to Plan → Taquilla → ProductLine → RoutingRevision → RoutingOperation.
3. Planned timestamps belong to APS only; actual timestamps remain MES-owned.
4. Capacity is finite when a resource is scheduled; overlapping use beyond available capacity is rejected or explicitly diagnosed.
5. Calendar non-working intervals, including configured breaks and off-shift time, are respected.
6. Solver/replanning results are deterministic for the same normalized input, configuration and algorithm version where deterministic mode is declared.
7. A what-if scenario cannot silently replace the published schedule.
8. Published schedules are immutable snapshots; later replans supersede rather than rewrite historical publication.
9. Missing or ambiguous planning inputs produce blockers/diagnostics rather than guessed values.
10. G4 remains usable before G6/G8/G9 by distinguishing evaluated constraints from unavailable future constraints.

## Planned slices

- **G4.1 — Scheduling Domain & Scenario Foundation — COMPLETED:** planning identities, scenario lifecycle, horizon, RBAC, audit and API baseline.
- **G4.2 — Demand / Routing Operation Expansion — COMPLETED:** exact G3 demand and G2 routing bindings materialized into immutable planning-operation snapshots with full provenance.
- **G4.3 — Calendar & Capacity Projection:** derive schedulable resource availability from G1 resources and G2 calendars, including breaks and off-shift intervals.
- **G4.4 — Finite-Capacity Sequencing Engine:** precedence, resource-capacity constraints, priorities, continuity and deterministic diagnostics.
- **G4.5 — Schedule Lifecycle / Replan / Publish:** draft solve, compare, publish, supersede and controlled replanning.
- **G4.6 — Gantt Projection & Frontend:** master/per-plan Gantt, zoom/scale, blockers and explainable schedule state.
- **G4.7 — What-if & Exception Evaluation:** isolated scenario changes, comparison metrics and explicit apply/discard workflow.
- **G4.8 — Gate Hardening:** regression, migration, solver invariants, RBAC/audit, deterministic replay, security, frontend and runtime evidence.

## G4 exit criteria

G4 becomes eligible for VALIDATED only when:
- planning objects have stable canonical identities and audited lifecycle;
- exact G3 demand and G2 routing provenance is preserved end-to-end;
- planning operations respect routing precedence;
- finite resource capacity and G2 calendar availability are enforced;
- configured non-working periods are never scheduled;
- schedule results expose blockers instead of inferring missing inputs;
- published schedule snapshots are immutable and supersedable;
- what-if scenarios remain isolated until explicit application;
- frontend Gantt is a projection of backend schedule state, not a second planning engine;
- G0/G1/G2/G3 regressions, G4 tests, schema drift, dependency/security audits and runtime regression are green;
- explicit release approval is received before merge/release.

## Current status

**G4 IN PROGRESS**

G4.1 is **COMPLETED**.

- implementation head: `9deed02de420f5e365e12fdf1729ff4691c4580a`;
- Alembic head: `0019_g4_1`;
- G4 APS push run #1: **SUCCESS**;
- scenario/run identity, horizon lifecycle, RBAC, audit and API foundation validated;
- no operation expansion, finite-capacity sequencing, Gantt or MES-owned actuals introduced.

G4.2 is **COMPLETED**.

- validated implementation head: `ecfa725d204f708444ffa37385809c864d9a97af`;
- Alembic head: `0020_g4_2`;
- G4 APS PR run #46: **SUCCESS**;
- exact Plan → Taquilla → ProductLine → RoutingRevision → RoutingOperation provenance preserved;
- deterministic input fingerprint and idempotent replay implemented;
- no planned timestamps, finite-capacity sequencing or MES actuals introduced.

Next slice: **G4.3 — Calendar & Capacity Projection**.
