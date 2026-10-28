# Prolowin Import Contract — Manufacturing Structure

Status: G0 contract baseline  
Version: 1.0.0  
Date: 2026-10-28

## Purpose
Define the stable boundary between a Prolowin extraction/parser and MOP canonical Master Data.

The first supported contract is the complete-structure report:
`Estructura del Artículo — Completa - Todos los Artículos`.

This contract is transport-independent: the source may originate from PDF/report extraction, CSV/XLSX export, or a future API, provided it produces the same normalized payload.

## Contract envelope

```json
{
  "schema_version": "1.0.0",
  "source_system": "PROLOWIN",
  "report_type": "COMPLETE_ARTICLE_STRUCTURE",
  "source": {
    "filename": "x-6111.pdf",
    "sha256": "...",
    "exported_at": "2026-10-28T09:46:00-03:00",
    "parser_version": "..."
  },
  "root_article": {
    "code": "X-6111",
    "description": "...",
    "quantity": "1.0000",
    "uom_raw": "UNID."
  },
  "rows": []
}
```

Quantities are serialized as decimal strings in transport to avoid floating-point loss.

## Row contract

Each row contains:
- `row_no`: stable sequential source-row number;
- `page`: source page when available;
- `article_code`;
- `operation_code`;
- `description_raw`;
- `quantity`: decimal string;
- `uom_raw`;
- `row_hash`: optional parser-produced deterministic hash.

Example:

```json
{
  "row_no": 63,
  "page": 2,
  "article_code": "14027",
  "operation_code": "FIN",
  "description_raw": "ALAMBRE CHICO RESPALDO MB F10",
  "quantity": "6.0000",
  "uom_raw": "UNID."
}
```

## Format-specific validations

For the validated complete-structure report format:

### Blocking
- source SHA-256 required;
- root article required;
- at least one row required;
- every row needs article_code, operation_code, quantity and UoM;
- quantity must parse as Decimal and be non-negative;
- exactly one `FIN` row per unique article code;
- exactly one FIN row must match the root article code.

### Warning/review
- description conflict for same code;
- non-FIN quantity differs from its FIN quantity;
- unknown operation code;
- unmapped UoM;
- fractional values in a count UoM;
- article kind remains UNKNOWN.

A warning may enter staging; a blocker cannot be applied to canonical Master Data.

## Normalization

```text
operation_code == FIN
  -> FlattenedArticleRequirementSnapshot

operation_code != FIN
  -> SourceOperationState
```

The root FIN row is marked `is_root=true` and excluded from component-demand totals.

## Idempotency

Import identity:
```text
source_system + source_sha256 + parser_version
```

Reimporting the same content must not create duplicate canonical revisions.

If the same source file is parsed by a newer parser version, the new parse may coexist in staging but canonical application requires reconciliation.

## Revision behavior

For each root/direct article structure:
1. normalize structure;
2. sort deterministically;
3. create SHA-256 fingerprint;
4. compare with currently active source fingerprint;
5. if unchanged -> no new revision;
6. if changed -> create candidate revision;
7. validate/reconcile;
8. approve/promote;
9. supersede previous revision without deleting it.

## Canonical application

The complete report alone can:
- discover/upsert Article masters;
- map raw UoM;
- provide operation evidence;
- provide a flattened reconciliation snapshot.

It **cannot alone author the recursive ComponentRelation tree**, because parent→child path information is lost in the flattened report.

Recursive BOM creation requires:
- direct article structures;
- direct parent/child export;
- or another source that preserves hierarchy.

## Reconciliation contract

A canonical BOM revision is eligible for approval when:
- no blocking DataQualityIssue exists;
- recursive explosion terminates without cycles;
- all required UoM mappings are resolved or explicitly accepted;
- its flattened projection matches the Prolowin FIN snapshot within configured exact/tolerance rules.

## Error response model

Every rejected or warning row returns:
- `rule_code`;
- severity;
- article_code;
- row_no;
- message;
- source value;
- suggested action when deterministic.

No row is silently discarded or silently corrected.
