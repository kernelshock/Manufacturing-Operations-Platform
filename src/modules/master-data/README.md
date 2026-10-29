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


Implemented in G2.2:
- ProductConfiguration as a one-to-one commercial/manufacturing projection of an exact FINISHED_PRODUCT Article;
- family and model codes/names;
- explicit product class;
- Decimal width with mandatory active canonical LENGTH UoM;
- human-readable configuration string;
- filtered read API and exact Article lookup;
- permission-driven frontend read surface;
- immutable audit event on configuration creation.

ProductConfiguration never becomes the BOM/Routing key: the exact Article/ArticleRevision remains authoritative.
