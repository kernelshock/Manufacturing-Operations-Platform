# ADR-0009 — Prospective Recalibration from a New Measured Baseline

Status: Accepted  
Date: 2026-10-27

## Context
FAIC confirms that:
- existing Kanban reorder points are not supported by current/verifiable calculations;
- replenishment quantities are likewise not supported by current/verifiable calculations;
- historical supplier evaluations were substantially subjective;
- no reliable historical dataset exists for supplier lead-time performance;
- therefore current card parameters cannot be traced to validated demand, supplier delay or current risk assumptions.

## Decision
All existing PP/PR and supplier lead-time/performance values are classified as:

`LEGACY_UNVERIFIED`

They may be preserved temporarily to avoid disrupting production, but they are not valid analytical baselines.

The Manufacturing Operations Platform will establish a **new prospective baseline** from measured operational events.

## Transition strategy

### Phase 0 — Preserve
Keep the current physical card and current PP/PR as operating safeguards during initial observation.

### Phase 1 — Measure
Start capturing, at minimum:
- Kanban trigger date/time;
- replenishment request date/time;
- authorization date/time;
- purchase-order reference/date;
- supplier promised date, when available;
- physical arrival date/time;
- receiving-inspection result;
- replenishment/return-to-container date/time;
- requested and received quantity;
- supplier;
- material/replenishment loop.

### Phase 2 — Compare
For each loop, show:
- legacy PP/PR;
- measured demand/consumption proxy;
- measured replenishment lead time;
- proposed PP/PR;
- variance;
- risk;
- observed stockout/shortage events;
- observed excess/overcoverage indicators.

### Phase 3 — Approve
No recalculated PP/PR becomes effective until reviewed and approved.

### Phase 4 — Improve
After a statistically useful observation period, use measured supplier performance and demand variability to recalibrate safety and replenishment policies.

## Supplier performance
Do not import historical subjective supplier scores as quantitative performance evidence.

A future supplier-performance model should derive objective indicators from measured events, such as:
- promised vs actual delivery;
- complete vs partial delivery;
- receiving conformity;
- rejection/return frequency;
- observed replenishment lead time;
- variability of lead time.

## Consequences
- G0/G2 must model data capture before optimization.
- G6 Materials must support legacy-vs-proposed comparison.
- Purchasing/Receiving must timestamp events required to build a trustworthy lead-time history.
- Historical cards remain operational safeguards during shadow mode, not analytical truth.
