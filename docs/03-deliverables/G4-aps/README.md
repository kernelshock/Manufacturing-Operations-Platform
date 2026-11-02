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
- **G4.3 — Calendar & Capacity Projection — COMPLETED:** schedulable resource candidates and exact calendar availability intervals projected from G1/G2, including breaks and off-shift gaps.
- **G4.4 — Finite-Capacity Sequencing Engine — COMPLETED:** deterministic precedence-aware scheduling, concrete resource assignment, finite-capacity occupancy and planned timestamps.
- **G4.5 — Schedule Lifecycle / Replan / Publish — COMPLETED:** governed replan lineage, comparison, immutable publication snapshots and explicit supersession.
- **G4.6 — Gantt Projection & Frontend — COMPLETED:** read-only master/per-plan Gantt, adjustable scale, productive-segment gaps and explainable published schedule state.
- **G4.7 — What-if & Exception Evaluation — COMPLETED:** isolated capacity hypotheses, baseline/candidate comparison and explicit apply/discard workflow.
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

G4.3 is **COMPLETED**.

- validated implementation head: `cf24d30aa5f1f20fc90bf9b01425e88b7b377cd8`;
- Alembic head: `0021_g4_3`;
- G4 APS PR run #82: **SUCCESS**;
- explicit assignment and work-center-pool resource semantics preserved;
- calendar hierarchy/effectivity, weekly windows, exceptions and lunch/off-shift gaps projected exactly;
- no planned operation timestamps or finite-capacity sequencing introduced.

G4.4 is **COMPLETED**.

- validated implementation head: `869e13c0b9d4aa70046aa21643ec375e46d92165`;
- Alembic head: `0022_g4_4`;
- G4 APS PR run #111: **SUCCESS**;
- planned start/finish and concrete resource assignment now belong to APS;
- operations may span multiple productive segments across breaks/off-shift gaps without consuming capacity there;
- routing precedence, finite resource occupancy and deterministic earliest-finish selection are enforced;
- MES-owned actuals and schedule publication remain outside G4.4.

G4.5 is **COMPLETED**.

- validated implementation head: `9dfe702dd7c4c7bc005e00db330102b1c5833fd8`;
- Alembic head: `0023_g4_5`;
- G4 APS push run #162: **SUCCESS**;
- calculated runs and published schedules are separate identities;
- replans require explicit provenance and reason from the currently published run;
- publication snapshots are immutable, versioned and supersedable;
- PostgreSQL enforces exactly one CURRENT publication per scenario;
- candidate replans can be compared to their published source before release.

G4.6 is **COMPLETED**.

- validated implementation head: `8d818af5c91b457cc265b02b5a8c8283b25209f0`;
- Alembic head remains `0023_g4_5`;
- G4 APS PR run #198: **SUCCESS**;
- APS is now a real permission-driven frontend module;
- master and per-plan Gantt views project only CURRENT published schedules;
- Hour / Shift / Day zoom changes visual density only, never planning semantics;
- productive segments preserve visible break/off-shift gaps inside operation envelopes;
- material, maintenance and workforce constraints are explicitly shown as not yet evaluated.

G4.7 is **COMPLETED**.

- validated implementation head: `c4fcf5047c8060ea6c68c72b75865589bc96fe80`;
- Alembic head: `0024_g4_7`;
- G4 APS push run #236: **SUCCESS**;
- what-if evaluation clones APS baseline snapshots rather than mutating or re-reading live G2/G3 inputs;
- RESOURCE_BLACKOUT and RESOURCE_CAPACITY_FACTOR hypotheses are isolated planning assumptions;
- Evaluate preserves the CURRENT publication;
- Apply explicitly publishes/supersedes through G4.5 governance;
- Discard leaves the published schedule untouched;
- frontend supports create, exception definition, evaluate, compare, apply and discard.

Next slice: **G4.8 — Gate Hardening**.
