# G5 — MES / Execution

Status: **IN PROGRESS**  
Started: 2026-11-02  
Base: released G4 main `19725298c4e04a8d1e7d1b69a05f58bef3e2d2ed`

## Objective

Convert the released APS plan into governed shop-floor execution evidence without allowing execution facts to rewrite planning history.

G5 owns the authoritative actual execution state for production operations:
- dispatchable execution work derived from released APS / G3 provenance;
- actual operation start, pause/resume and finish;
- actual produced quantity and scrap;
- setup / productive / interruption time evidence;
- transfer / handoff and WIP traceability;
- execution deviation and delay evidence;
- rework / alternative execution-path evidence where explicitly governed;
- shop-floor operator interaction and execution projection;
- feedback from execution to planning without mutating published APS history.

## Inputs owned by previous gates

G5 consumes, but does not duplicate:
- G1 Plant / Area / WorkCenter / Resource / identity / RBAC / audit;
- G2 Article / RoutingRevision / RoutingOperation / ResourceAssignment;
- G3 Plan / Taquilla / ProductLine / deck / routing binding;
- G4 published schedule, planned operation sequence, planned resource and planned timestamps.

## Ownership boundaries

### G5 owns
- actual shop-floor execution identity;
- actual start / pause / resume / finish timestamps;
- actual produced quantity;
- actual scrap / rejected quantity;
- optional setup evidence;
- interruption / delay reason evidence;
- execution resource actually used;
- WIP transfer / handoff evidence;
- execution traceability by Plan / Taquilla / ProductLine / RoutingOperation;
- governed deviation from the planned operation/resource/sequence;
- operator-facing rapid execution capture.

### G5 does not own
- G2 master definitions;
- G3 requested demand;
- G4 planned timestamps, published schedule or what-if state;
- G6 inventory/material truth;
- G7 purchasing;
- G8 authoritative maintenance work orders/downtime;
- G9 workforce master / skills / attendance.

G5 may reference maintenance/workforce/material context once those later gates exist, but it must not fabricate their authoritative state.

## Non-negotiable rules

1. Planned timestamps remain G4-owned; G5 records separate actual timestamps.
2. Execution evidence never rewrites a published G4 schedule.
3. Every execution record retains provenance to Plan → Taquilla → ProductLine → RoutingRevision → RoutingOperation and, where applicable, published APS operation.
4. Actual quantities use Decimal-safe semantics and cannot be silently inferred from planned quantities.
5. Actual start/finish must come from explicit execution events or governed historical assimilation.
6. Operator capture must remain fast and minimal while backend validation remains authoritative.
7. Rework or alternative paths are explicit execution evidence; they are never inferred by changing the original routing history.
8. Next-operation eligibility may depend on predecessor execution completion, but the dependency must remain explainable and auditable.
9. Missing execution facts remain unknown; G5 must not fabricate produced quantity, scrap, timestamps, operator, resource or delay reason.
10. Materials, maintenance and workforce constraints remain unavailable/not evaluated until their authoritative gates are released.

## Planned slices

- **G5.1 — Execution Domain & Dispatch Foundation — COMPLETED:** canonical dispatch/execution-operation identities, CURRENT-publication materialization, lifecycle, RBAC, audit and API baseline.
- **G5.2 — Operation Start / Finish & Quantity Capture — COMPLETED:** explicit START/COMPLETE events, actual timestamps, produced quantity, idempotent lifecycle and audit.
- **G5.3 — Setup / Pause / Interruption / Deviation — COMPLETED:** optional setup, repeatable pause/resume interruptions, actual-resource evidence and observational plan-vs-actual deviations.
- **G5.4 — Transfer / Handoff & WIP Traceability:** predecessor/successor handoff, WIP movement and operation-to-operation traceability.
- **G5.5 — Rework & Alternative Execution Path:** explicit repair/rework loops and governed deviation from nominal routing without rewriting G2/G3 history.
- **G5.6 — APS Feedback & Completion Classification:** actual-vs-planned timing, delay classification and feedback to replanning without mutating published G4 schedules.
- **G5.7 — Shop-floor Frontend & Rapid Tracking:** operator-first start/finish/quantity interaction plus leader/manager execution projection.
- **G5.8 — Gate Hardening:** migration integrity, execution invariants, RBAC/audit, regressions, frontend, security and runtime evidence.

## G5 exit criteria

G5 becomes eligible for VALIDATED only when:
- actual execution identities are stable and auditable;
- planned vs actual ownership is unambiguous;
- exact G2/G3/G4 provenance is preserved;
- start/finish and quantity capture are explicit and validated;
- predecessor/successor execution traceability is enforced;
- rework/alternative execution does not rewrite canonical routing history;
- operator workflows are permission-protected and auditable;
- no G6/G8/G9 authoritative facts are fabricated;
- G0–G4 regressions, G5 tests, schema drift, dependency/security audits, frontend and runtime validation are green;
- explicit release approval is received before merge/release.

## Current status

**G5 IN PROGRESS**

G5.1 is **COMPLETED**.

- validated implementation head: `74d149ed41afe9df8822c9820ff8bfad1169bdec`;
- Alembic head: `0025_g5_1`;
- G5 MES push run #5: **SUCCESS**;
- one canonical execution dispatch per CURRENT APS publication;
- exact G2/G3/G4 provenance copied into MES execution-operation snapshots;
- DRAFT → RELEASED / CANCELLED lifecycle;
- dispatch materialization and release replay are idempotent;
- release revalidates that the source APS publication remains CURRENT;
- G5.1 stores planned evidence only and introduces no actual start/finish, produced quantity, scrap, pause/setup, operator or actual-resource state;
- `mes.read` / `mes.edit` and audited dispatch mutations are active.

G5.2 is **COMPLETED**.

- validated implementation head: `4957868d221f068e17fa337b1f92f92dc732bc0c`;
- Alembic head: `0026_g5_2`;
- G5 MES push run #31: **SUCCESS**;
- operation lifecycle: PENDING → RUNNING → COMPLETED;
- START/COMPLETE are explicit MES events with actor/time evidence;
- actual start/finish remain separate from G4 planned timestamps;
- produced quantity is explicit Decimal-safe actual data and may differ from requested quantity;
- no scrap is inferred from quantity variance;
- replay of identical START/COMPLETE is idempotent;
- conflicting completion evidence is rejected;
- G5.2 still excludes pause/setup/interruption/scrap/actual-resource deviation.

G5.3 is **COMPLETED**.

- validated implementation head: `7aba83e03e32ed887511a880214c55c365d68614`;
- Alembic head: `0027_g5_3`;
- G5 MES push run #63: **SUCCESS**;
- optional setup is explicit and must close before operation START;
- operation lifecycle now supports RUNNING ↔ PAUSED with repeatable interruption history;
- every pause requires an explicit reason code;
- at most one interruption can remain open per operation;
- actual resource remains unknown unless explicitly supplied;
- alternate actual resource requires a deviation reason and never rewrites planned resource;
- deviation projection derives start/finish/quantity/resource/setup/interruption deltas without automatic causal classification;
- G5.3 still excludes G8 maintenance authority, G9 workforce authority and G5.4 WIP handoff.

The next slice is:

**G5.4 — Transfer / Handoff & WIP Traceability**
