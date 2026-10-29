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


Implemented in G2.3:
- canonical Supplier identity with a stable supplier code;
- legal/trade names and broad PRODUCT / PROCESS / SERVICE / MIXED classification;
- source-system mappings so Prolowin, CRM and later imports can point to one canonical Supplier;
- REVIEW_REQUIRED source records for duplicate/consolidation workflows without inventing a match;
- SupplierArticle sourcing relation with supplier article code, preferred flag, lead time, MOQ and canonical order UoM;
- permission-driven supplier read surface inside Datos maestros;
- immutable audit events for supplier, source-mapping and supplier-article creation.

Purchasing transactions, prices, approvals, receipts and supplier evaluation remain owned by the future Purchasing module.


Implemented in G2.4:
- revisioned BOMs tied to exact ArticleRevision identities;
- immutable published component structures (only DRAFT BOMs may receive components);
- Decimal(24,8) component quantities and source-UoM preservation;
- optional canonical UoM, pinned child revision, sequence, idempotency relation key, scrap and line effectivity;
- controlled publish/supersede lifecycle;
- effectivity-aware recursive explosion;
- path provenance retained before aggregation;
- indirect cycle detection;
- ambiguity rejection when an unpinned child Article has multiple effective active BOMs.

The complete Prolowin report remains reconciliation evidence only. It does not author parent-child edges because that report is flattened.


Implemented in G2.5:
- revisioned Routing/BOP definitions tied to exact ArticleRevision identities;
- source operation code/description preserved separately from BOM demand;
- operation classification into PHYSICAL_PRODUCTION, COSTING_ONLY, ADMINISTRATIVE, COMPLETION_MARKER or UNKNOWN;
- APS-facing schedulable flag and explicit completion-marker semantics;
- optional Decimal nominal rate + rate UoM;
- references to G1 Area and WorkCenter;
- ResourceAssignment references G1 Resource directly and validates hierarchy;
- one optional principal resource per operation at the service boundary;
- immutable published routings with controlled publish/supersede lifecycle;
- effectivity-aware effective-routing lookup and definition projection.

A standalone canonical Process master is not invented in G2.5. The optional process_id from the G0 physical baseline remains deferred until Process has its own identity/governance contract.


Implemented in G2.6:
- versioned manufacturing calendars bound to exactly one G1 Plant, Area, WorkCenter or Resource;
- IANA timezone identity per calendar series;
- local weekly availability windows with Decimal capacity factor and overnight-shift support;
- dated CLOSED and AVAILABLE_OVERRIDE exceptions;
- deterministic resolution precedence Resource > WorkCenter > Area > Plant;
- exception precedence over recurring weekly windows;
- immutable ACTIVE calendars with controlled supersede/effectivity;
- availability resolution returns nominal capacity evidence for APS without creating or modifying APS schedules.

Calendar effectivity is day-granular; recurring windows are minute-granular in the calendar's local timezone. APS remains responsible for order sequencing, finite scheduling and transactional schedule state.


Implemented in G2.7:
- Prolowin ImportBatch identity by source SHA-256 + parser version;
- PostgreSQL append-only guards for staged complete-report rows and direct parent-child relations;
- complete-report FIN normalization into flattened requirement snapshots;
- non-FIN rows retained independently as SourceOperationState routing evidence;
- DataQualityIssue quarantine with INFO/WARNING/ERROR/BLOCKER severity and explicit rule codes;
- governed raw-UoM alias discovery without silently inventing canonical mappings;
- global Article reuse by exact Prolowin business code;
- content-addressed root ArticleRevision evidence for complete reports;
- direct-structure reachability/duplicate/cycle validation;
- DRAFT ArticleRevision/BOMRevision/BOMComponent candidates from direct hierarchy only;
- Decimal-safe candidate recursive explosion and FIN reconciliation with approved UoM conversion factors;
- per-item reconciliation evidence and MATCH / MATCH_WITH_WARNINGS / MISMATCH / BLOCKED outcomes;
- non-proprietary five-product reference-corpus metadata fixture and X-6111/14027 trace regression.

The complete Prolowin report remains a reconciliation oracle and never authors parent-child BOM relationships. SourceOperationState is evidence for later routing mapping; G2.7 does not guess WorkCenter/Resource assignments from operation codes.
