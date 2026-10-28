# Master Data / BOM / BOP — Relational Physical Schema Baseline

Status: G0 architecture baseline  
Date: 2026-10-28  
Scope: canonical manufacturing definition and Prolowin assimilation

This document defines a relational baseline independent of the final application stack. SQL types are indicative and may be adapted when DEC-007 is resolved.

## 1. Ownership

**Master Data owns manufacturing definition:**
- Article
- ArticleRevision
- UnitOfMeasure
- BOMRevision
- BOMComponent
- RoutingRevision
- RoutingOperation
- ResourceAssignment
- source-to-canonical mappings

Consumers:
- Materials reads effective BOMs and exploded demand;
- APS reads effective routings/resources;
- MES executes published operations;
- Intelligence reads versioned projections.

No consumer module may maintain an independent copy of BOM or Routing truth.

## 2. Core Article master

### `md_article`

| Column | Type | Rule |
|---|---|---|
| id | UUID | PK, immutable |
| external_system | VARCHAR(40) | e.g. PROLOWIN |
| external_code | VARCHAR(80) | Prolowin business key |
| canonical_description | TEXT | current normalized description |
| article_kind | VARCHAR(30) | UNKNOWN, PURCHASED, MANUFACTURED, FINISHED_PRODUCT, CONSUMABLE, SERVICE |
| default_uom_id | UUID nullable | FK md_uom |
| active | BOOLEAN | default true |
| first_seen_at | TIMESTAMPTZ | audit |
| last_seen_at | TIMESTAMPTZ | audit |
| created_at | TIMESTAMPTZ | audit |
| updated_at | TIMESTAMPTZ | audit |

Constraints:
- unique(`external_system`, `external_code`);
- prefixes such as A-, B-, X-, numeric, etc. are not authoritative classifications.

### `md_article_revision`

| Column | Type | Rule |
|---|---|---|
| id | UUID | PK |
| article_id | UUID | FK md_article |
| revision_label | VARCHAR(80) nullable | explicit revision if source provides one |
| source_fingerprint | CHAR(64) | SHA-256 of normalized manufacturing definition |
| valid_from | TIMESTAMPTZ | effectivity |
| valid_to | TIMESTAMPTZ nullable | null = open |
| status | VARCHAR(20) | DRAFT, ACTIVE, SUPERSEDED, REJECTED |
| source_batch_id | UUID | provenance |
| approved_at | TIMESTAMPTZ nullable | governance |
| approved_by | UUID nullable | user/role reference |

If Prolowin does not expose a reliable revision identifier, MOP creates a **content-addressed revision** from the normalized source fingerprint. A changed structure creates a new revision; it does not overwrite historical definition.

## 3. Units of measure

### `md_uom`
- id UUID PK
- code VARCHAR(30) unique
- dimension VARCHAR(30): COUNT, LENGTH, MASS, VOLUME, OTHER
- canonical BOOLEAN
- active BOOLEAN

### `md_uom_alias`
- id UUID PK
- source_system VARCHAR(40)
- raw_value VARCHAR(80)
- uom_id UUID nullable
- mapping_status VARCHAR(20): MAPPED, UNMAPPED, REVIEW_REQUIRED
- conversion_factor DECIMAL(24,12) nullable
- approved_at / approved_by

Examples of source values observed:
`UNID.`, `MTS`, `MTS 3`, `LITROS`, `KGS.`, `GRAMOS`, `BARRA`, `BARRAS`, `PLANCH`.

Source values are never discarded.

## 4. BOM / ABM

### `md_bom_revision`

| Column | Type |
|---|---|
| id | UUID PK |
| parent_article_revision_id | UUID FK |
| revision_no | INTEGER |
| valid_from | TIMESTAMPTZ |
| valid_to | TIMESTAMPTZ nullable |
| status | VARCHAR(20) |
| source_system | VARCHAR(40) |
| source_batch_id | UUID |
| source_fingerprint | CHAR(64) |

Unique active BOM per exact ArticleRevision and effectivity window.

### `md_bom_component`

| Column | Type | Rule |
|---|---|---|
| id | UUID | PK |
| bom_revision_id | UUID | FK |
| child_article_id | UUID | FK md_article |
| child_revision_id | UUID nullable | pin when source defines revision |
| quantity | DECIMAL(24,8) | > 0 |
| source_uom_raw | VARCHAR(80) | immutable source text |
| uom_id | UUID nullable | approved mapping |
| sequence_no | INTEGER nullable | source/order hint |
| source_relation_key | VARCHAR(200) nullable | idempotency |
| scrap_factor | DECIMAL(12,8) nullable | future/explicit only |
| effective_from | TIMESTAMPTZ nullable | optional line effectivity |
| effective_to | TIMESTAMPTZ nullable | optional |

Unique idempotency key:
`(bom_revision_id, source_relation_key)` when available.

### Recursive rule

A child may itself have an active BOM.

```text
X-6111
  -> A-621 x2
       -> ...
  -> B-806 x2
       -> SB-601 ...
  -> ...
```

The explosion engine must:
- multiply quantities through every level;
- detect cycles;
- retain path provenance;
- aggregate only after the path calculation;
- preserve original UoM until mapping/conversion is approved.

## 5. Routing / BOP

### `md_routing_revision`
- id UUID PK
- article_revision_id UUID FK
- revision_no INTEGER
- valid_from / valid_to
- status
- source_system
- source_batch_id
- source_fingerprint

### `md_routing_operation`

| Column | Type | Rule |
|---|---|---|
| id | UUID | PK |
| routing_revision_id | UUID | FK |
| source_operation_code | VARCHAR(30) | 010, 020, 025... |
| sequence_no | INTEGER | canonical sequence |
| source_description | TEXT | preserved |
| process_id | UUID nullable | canonical process |
| area_id | UUID nullable | canonical area |
| work_center_id | UUID nullable | canonical work center |
| operation_kind | VARCHAR(30) | PHYSICAL_PRODUCTION, COSTING_ONLY, ADMINISTRATIVE, COMPLETION_MARKER, UNKNOWN |
| schedulable | BOOLEAN | APS eligibility |
| completion_marker | BOOLEAN | true for normalized FIN marker unless validated otherwise |
| nominal_rate | DECIMAL(24,8) nullable | if available |
| rate_uom | VARCHAR(50) nullable | source/canonical rate unit |
| active | BOOLEAN | |

Unique:
`(routing_revision_id, sequence_no)`.

### `md_resource_assignment`
- id UUID PK
- routing_operation_id UUID FK
- resource_id UUID FK
- principal BOOLEAN
- capacity_factor nullable
- source_batch_id UUID

## 6. Product/configuration relation

### `md_product_configuration`
A finished article can be represented as a commercial/manufacturing configuration without duplicating its article identity.

Fields:
- id UUID PK
- article_id UUID FK
- family_code / family_name
- model_code / model_name
- class
- width nullable
- configuration_string
- active

The exact finished article/revision remains the key used for BOM and Routing.

## 7. Prolowin staging

### `int_import_batch`
- id UUID PK
- source_system
- source_type
- source_filename
- source_sha256
- exported_at nullable
- imported_at
- parser_version
- mapping_version
- imported_by
- status: RECEIVED, PARSED, VALIDATED, REJECTED, APPLIED, RECONCILED
- accepted_rows
- rejected_rows

### `int_prolowin_structure_row`
- id UUID PK
- batch_id UUID FK
- root_article_code
- source_page nullable
- source_row_no
- article_code
- operation_code
- description_raw
- quantity DECIMAL(24,8)
- uom_raw
- raw_payload JSON/TEXT nullable
- row_hash CHAR(64)

Unique:
`(batch_id, row_hash)`.

### `int_prolowin_complete_snapshot`
- id UUID PK
- batch_id UUID FK
- root_article_code
- root_quantity
- root_uom_raw
- report_timestamp nullable
- source_sha256

### `int_prolowin_flat_requirement`
Generated only after the report-format validation succeeds:
- snapshot_id UUID
- article_code
- quantity
- uom_raw
- source_fin_row_id UUID
- is_root BOOLEAN

Unique:
`(snapshot_id, article_code)`.

### `int_source_operation_state`
Derived from non-FIN rows:
- snapshot_id
- article_code
- source_operation_code
- source_description
- quantity
- uom_raw
- source_row_id

These records are routing evidence, not additive material demand.

## 8. Data quality

### `dq_issue`
- id UUID PK
- batch_id UUID
- entity_type
- entity_key
- rule_code
- severity: INFO, WARNING, ERROR, BLOCKER
- message
- source_row_id nullable
- status: OPEN, ACCEPTED, RESOLVED, WAIVED
- resolution_note nullable
- resolved_by / resolved_at nullable

Initial rule codes:
- `PLW_FIN_MISSING`
- `PLW_FIN_DUPLICATE`
- `PLW_ROOT_NOT_IDENTIFIED`
- `PLW_UOM_UNMAPPED`
- `PLW_QTY_INVALID`
- `PLW_DESCRIPTION_CONFLICT`
- `PLW_BOM_CYCLE`
- `PLW_OPERATION_SEQUENCE_UNKNOWN`
- `PLW_RECONCILIATION_MISMATCH`

## 9. Reconciliation

### `int_reconciliation_run`
- id UUID PK
- batch_id
- root_article_revision_id
- bom_revision_id
- run_at
- status: MATCH, MATCH_WITH_WARNINGS, MISMATCH, BLOCKED
- compared_items
- matching_items
- mismatching_items

### `int_reconciliation_item`
- reconciliation_run_id
- article_code
- source_fin_quantity
- source_uom_raw
- calculated_quantity
- calculated_uom_id/raw
- variance
- result

The recursive canonical explosion should match the validated FIN projection after approved UoM conversions and explicit exclusions.

## 10. No-delete and audit rule

Manufacturing definitions are versioned, never silently overwritten.

Transactional history (plans, taquillas, executions, Kanban cycles) keeps the revision IDs that were effective at the time. This guarantees that future master-data changes cannot rewrite historical production truth.
