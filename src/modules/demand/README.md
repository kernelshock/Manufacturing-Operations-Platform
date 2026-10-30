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


Implemented in G3.2:
- TaquillaProductLine with stable UUID identity;
- exact reference to G2 Article;
- active FINISHED_PRODUCT validation;
- Decimal(24,8) requested quantity;
- explicit positive sequence number unique within the Taquilla;
- optional source_line_key for idempotent import/replay;
- DRAFT-only composition mutation;
- composition freeze once the Taquilla leaves DRAFT;
- REST create/list/update operations protected by demand RBAC;
- append-only audit evidence for composition create/update;
- Alembic migration `0014_g3_2`.

G3.2 does not infer or copy ProductConfiguration, does not allocate products to vehicle decks, and does not create APS schedule state.


Implemented in G3.3:
- explicit Taquilla vehicle topology: SIMPLE or DOUBLE_DECK;
- explicit product-line deck position: SINGLE / UPPER / LOWER;
- SIMPLE ↔ SINGLE and DOUBLE_DECK ↔ UPPER/LOWER service validation;
- optional source_document_key independent from deck allocation;
- DRAFT-only topology changes, blocked after composition exists;
- audited topology and line-deck/source-document mutations;
- Alembic migration `0015_g3_3`.

No deck position is inferred from product code, line order, source-document order or source-document identity. Source-document grouping is provenance only.
