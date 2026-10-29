# demand

Status: **in progress — G3**.

This bounded module owns the operational demand identities that connect released Master Data definitions to later APS/MES execution.

G3 ownership:
- Production Plan;
- Taquilla;
- requested product composition;
- explicit vehicle/deck demand topology;
- selected/effective G2 RoutingRevision binding;
- source provenance and administrative demand lifecycle.

Boundaries:
- G2 remains owner of Article/ProductConfiguration/BOM/Routing/calendar definitions;
- G4 APS owns finite-capacity sequencing and planned timestamps;
- G5 MES owns actual execution;
- G6/G7 own inventory/replenishment and purchasing effects.

The first implementation slice is G3.1 — Production Plan & Taquilla Foundation.


Implemented in G3.1:
- ProductionPlan with stable UUID identity and editable business plan number;
- Taquilla with stable UUID identity, globally unique business code and explicit sequence inside a Plan;
- one-to-many Plan → Taquilla membership;
- controlled non-reversible lifecycle transitions;
- terminal-state identity protection;
- global `demand.read` / `demand.edit` RBAC capabilities;
- authenticated REST API and append-only audit integration;
- Alembic migration `0013_g3_1`.

G3.1 deliberately does not store product lines, deck allocation, routing selection, APS timestamps or MES actuals.
