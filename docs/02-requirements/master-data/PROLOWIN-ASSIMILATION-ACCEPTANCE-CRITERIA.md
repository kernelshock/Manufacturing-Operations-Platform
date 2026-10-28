# Prolowin Manufacturing-Definition Assimilation — Acceptance Criteria

Status: G0 requirement baseline  
Date: 2026-10-28

## Objective
Assimilate the complete Prolowin manufacturing-definition base without corrupting product structure, double-counting operation stages, duplicating shared articles or rewriting historical revisions.

## AC-01 — Source preservation
Every import has filename, SHA-256, parser version, timestamp and immutable source rows.

## AC-02 — Global Article identity
The same Prolowin code maps to one canonical Article identity across all products.

## AC-03 — No prefix inference
Article kind is never accepted solely because of code prefix. Classification uses source structure and/or approved mapping.

## AC-04 — Decimal-safe quantities
All quantities are parsed with decimal semantics; binary floating-point is prohibited for stored source quantities and BOM quantities.

## AC-05 — UoM preservation
Raw Prolowin UoM is retained even when no canonical mapping exists.

## AC-06 — FIN normalization
For the validated complete report format:
- one and only one FIN row exists per unique article code;
- non-FIN rows are not added to material demand;
- root FIN is excluded from component demand.

## AC-07 — Routing separation
Operation stages are stored as routing evidence independently of BOM demand.

## AC-08 — Recursive BOM
Canonical BOM supports arbitrary depth and detects cycles.

## AC-09 — Exact configuration
BOM is attached to the exact finished ArticleRevision/configuration. Family similarity cannot substitute missing structure.

## AC-10 — Revision safety
Changed source structure creates a candidate revision; it does not overwrite the active historical revision.

## AC-11 — Idempotency
Reimporting identical content does not duplicate Articles, revisions or ComponentRelations.

## AC-12 — Reconciliation
For an approved direct parent-child import, recursive canonical explosion must reconcile with the complete Prolowin FIN projection.

## AC-13 — Data-quality quarantine
Blocking anomalies remain in staging and cannot enter active canonical manufacturing definition.

## AC-14 — Known regression corpus
At minimum, automated importer regression tests must cover:
- X-1148
- X-1149
- X-2209
- X-6111
- X-7070

## AC-15 — Kanban traceability
Material 14027 in X-6111 must be traceable from finished product demand to its final material requirement and then to the applicable ReplenishmentLoop/Kanban policy once that loop mapping is configured.

## Exit condition for bulk assimilation
Bulk assimilation is permitted only after the five-product corpus passes parser, normalization and reconciliation tests with zero unresolved blockers.
