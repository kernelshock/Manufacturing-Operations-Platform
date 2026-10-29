# master-data

Status: **in progress — G2**.

This bounded module owns canonical manufacturing definition for MOP.

Implemented in G2.1:
- UnitOfMeasure;
- UnitOfMeasureAlias with source-system/raw-value preservation;
- Article global identity by external system + external code;
- ArticleRevision candidate records identified by source fingerprint;
- global `masterdata.read` / `masterdata.edit` capabilities;
- server-side API authorization and append-only audit events.

Important boundaries:
- code prefixes never infer article kind;
- new article revisions begin as DRAFT; activation/approval is not implicit;
- no delete/update endpoint is introduced for historical definitions;
- Resource remains owned by G1 Core and is only referenced by later Routing/BOP records;
- raw FAIC/Prolowin source files remain outside the public repository.
