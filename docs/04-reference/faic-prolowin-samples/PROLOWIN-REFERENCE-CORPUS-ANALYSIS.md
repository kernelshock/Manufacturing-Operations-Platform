# Prolowin Complete-Structure Corpus Analysis — Five Products

Status: G0 validated reference analysis  
Date: 2026-10-28

## Corpus
Five complete Prolowin product-structure reports were reviewed visually and textually:
- X-1148 — Enterprise double
- X-1149 — Enterprise single
- X-2209 — Moonraker Semicama
- X-6111 — Apollo
- X-7070 — Discovery

The PDFs supersede earlier screenshot-only samples.

## Extracted structural statistics

| Product | Pages | Source rows | Unique article codes | FIN rows | Non-FIN operation rows | Multistage codes |
|---|---:|---:|---:|---:|---:|---:|
| X-1148 | 7 | 230 | 194 | 194 | 36 | 20 |
| X-1149 | 7 | 222 | 186 | 186 | 36 | 20 |
| X-2209 | 6 | 210 | 187 | 187 | 23 | 16 |
| X-6111 | 5 | 175 | 147 | 147 | 28 | 20 |
| X-7070 | 5 | 172 | 149 | 149 | 23 | 18 |

Counts refer to the rows extracted from this exact PDF corpus.

## Invariant observed across all five documents

For every unique article code present in a report, the corpus contains **exactly one `FIN` row**.

Codes that have additional rows use source operation codes such as:
- 010
- 020
- 025
- 030
- 040
- 050

No code in this five-document corpus has more than one `FIN` row.

This gives a robust normalization rule for this report format:

```text
All source rows
   |
   +--> non-FIN rows -> operation/routing evidence
   |
   +--> FIN row      -> final article quantity in flattened complete projection
```

The root article itself also appears as a FIN row and must be excluded from component-demand summation.

## Important limitation

The complete report is a **flattened projection**. It identifies all articles involved in one finished product and exposes operation states, but it does not preserve the complete parent→child path for every row.

Therefore it cannot by itself reconstruct the recursive BOM hierarchy.

Preferred architecture:
1. import direct parent-child structure from Prolowin tables/native article structures;
2. recursively build the canonical BOM;
3. normalize routing separately;
4. explode the canonical BOM;
5. reconcile the result against this complete report.

## Strong evidence for a global Article master

Across the five finished products, the corpus contains 436 distinct non-root FIN article codes.

Distribution:
- 193 appear in only one reference product;
- 149 appear in two products;
- 44 appear in three products;
- 15 appear in four products;
- 35 appear in **all five products**.

Therefore 243 of 436 observed article codes are reused by at least two reference products.

Examples shared across all five include:
`0156`, `0311`, `0398`, `13102`, `13437`, `13560`, `14063M`, `14073`, `14180`, `1423`, `1426`, `14639`, `14642`, `14643`, `15277`, `16077`, `16290`, `17273`, `17342`, `17686`, `18055`, `18627L`, `2160`, `3947`, `3955`, `3960`, `4177`, `4194`, `4338`, `5434`, `5692G`, `8003`, `8026`, `8135`, `9379`.

This validates:
- one canonical Article record per Prolowin business code;
- reuse through BOM relations;
- no duplication of the same component master inside each product.

## Cross-product similarity is useful but not authoritative

Observed pairwise overlap of non-root FIN codes includes:
- X-1148 vs X-1149: 164 shared codes;
- X-6111 vs X-7070: 99 shared codes;
- X-2209 vs X-7070: 82 shared codes.

This supports family/platform analysis and common-component analytics, but exact configuration BOM remains authoritative.

## Material-to-Kanban bridge: code 14027

The X-6111 Apollo complete report includes:
`14027 — ALAMBRE CHICO RESPALDO MB F10 — 6.0000 UNID.`

This is the same material code observed on the physical Kanban card examined during G0.

Therefore MOP can eventually derive planned consumption for that Kanban loop as:

```text
planned X-6111 quantity × 6 units
+ demand from every other product consuming 14027
= projected demand for material 14027
```

The physical card PP/PR remain LEGACY_UNVERIFIED until recalibrated, but the demand side can be traced to released production.

## BOM versus routing confirmed

Examples across the corpus show repeated operation states:
- cut/perforate;
- bend/form;
- weld;
- upholstery operations;
- final completion.

X-2209 is particularly explicit:
`A-208` goes through BALAN → CORTE → COSTU → PEGAD → ENFUN → FIN.

Therefore:
- FIN quantities feed flattened BOM reconciliation;
- non-FIN operation rows feed BOP/routing reconstruction;
- the two domains remain separate but linked to the same Article/Revision.

## Units of measure

Observed source units include, among others:
- UNID.
- MTS
- MTS 3
- LITROS
- KGS.
- GRAMOS
- BARRA / BARRAS
- TIRAS
- PLANCH

Source UoM must be preserved verbatim in staging and mapped through a governed canonical UoM table.

## Data-quality behavior

The importer must not silently repair suspicious values or units.

Any of the following creates a DataQualityIssue:
- missing FIN row for a code in this report format;
- more than one FIN row for a code;
- root article not identifiable;
- invalid/nonmapped UoM;
- impossible quantity;
- source code missing from Article master;
- conflicting descriptions for one code outside accepted revision/effectivity rules;
- recursive cycle in native parent-child structure.

## Initial ingestion layers

```text
PROLOWIN EXPORT / REPORT
        |
        v
RawImportBatch
        |
        v
SourceStructureRow
        |
        +--> FIN projection
        |      -> FlattenedArticleRequirementSnapshot
        |
        +--> operation rows
               -> SourceOperationState
                      |
                      v
                routing mapping
```

Native parent-child structures then populate:
`BOMRevision + ComponentRelation`.

## Acceptance principle for full-base assimilation

Do not bulk-import the complete Prolowin database directly into canonical masters.

Use:
1. raw immutable batch;
2. parser validation;
3. normalization;
4. data-quality queue;
5. canonical upsert;
6. recursive explosion;
7. reconciliation against complete-structure report;
8. approval/evidence.

The five-product corpus becomes the initial regression fixture for that importer.
