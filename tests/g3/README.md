# G3 tests

This directory contains automated validation for G3 — Demand / Plan / Taquilla / Routing.

The bootstrap test locks the approved ownership boundaries before transactional implementation begins. Later G3 slices add schema, integration, API, RBAC, audit and runtime coverage here.


## G3.8 gate hardening

The final gate includes `test_gate_hardening.py`, which makes cross-slice exit invariants executable:
- all completed G3 slices are recorded;
- G3 demand code does not introduce APS planned timestamps/capacity or MES actuals;
- demand APIs retain demand.read/demand.edit authorization boundaries;
- required mutation audit actions remain present;
- assimilation retains explicit source/deck/idempotency semantics;
- the frontend remains permission-driven and explicitly excludes APS scheduling ownership.

The GitHub Actions workflow executes this hardening suite both as part of the complete G3 suite and as a dedicated pre-gate step.
