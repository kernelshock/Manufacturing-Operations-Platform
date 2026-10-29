# Prolowin Integration Baseline

Status: Confirmed baseline / API capability pending vendor verification  
Date: 2026-10-27

## Confirmed operational use in Prolowin
- Articles/materials reference
- Suppliers
- Purchase orders
- Supplier follow-up / delay claims

## Important limitation
Prolowin has stock capability, but FAIC does not currently use it to manage operational stock.

Formal remittances, invoices and payments are handled in **Tango**, which remains outside the current project scope.

## Confirmed access methods
- Excel table exports
- CSV table exports
- Queries through the Prolowin user interface
- Reports generated from the interface

## Initial integration architecture

```text
PROLOWIN
   |
   | CSV / XLSX / controlled reports
   v
INGESTION / STAGING
   |
   | schema validation
   | column mapping
   | code normalization
   | deduplication
   | batch audit
   v
CANONICAL INTEGRATION MODEL
   |
   +--> Materials
   +--> Purchasing
   +--> APS material constraints
   +--> Intelligence / reconciliation
```

## Required import-batch metadata
- import_batch_id
- source_system = PROLOWIN
- source_file
- source_file_hash
- exported_at, when available
- imported_at
- mapping_version
- imported_by
- accepted_rows
- rejected_rows
- reconciliation_status

## Freshness
FAIC indicates that practical Prolowin exports can be obtained **daily or weekly**.

This cadence is acceptable for:
- purchasing follow-up;
- supplier-delay monitoring;
- purchase-order reconciliation;
- supplier/material reference updates.

It is **not sufficient as the sole source for near-real-time physical stock availability** required by APS/Materials decisions.

Therefore:
- Prolowin synchronization is batch-oriented;
- stock availability for production requires a separate operational stock source/ledger;
- the platform must display the timestamp/age of imported purchasing data.

## API research result
No reliable public documentation was found that can be attributed with confidence to the Prolowin product used at FAIC. Therefore, the project must not infer that an API exists or does not exist.

### Verification action
Contact the vendor/support or inspect installed-version technical documentation and administration options. Questions:
1. Is there a REST/SOAP/OData or other supported API?
2. Is API access included in FAIC's license/version?
3. Which entities are exposed?
4. Read-only or read/write?
5. Authentication method?
6. Rate limits?
7. Webhooks/events?
8. Direct database access supported?
9. Stable scheduled CSV/XLSX export available?
10. Vendor-supported integration practices?


## Manufacturing-definition contract

The normalized transport contract is defined in:
- `integrations/prolowin/contracts/IMPORT-CONTRACT.md`
- `integrations/prolowin/contracts/complete-structure-batch.schema.json`
- `integrations/prolowin/contracts/direct-structure-batch.schema.json`

The transport is deliberately independent of PDF/CSV/XLSX/API. Every adapter must produce the same normalized contract before canonical application.

Canonical application targets **Master Data**. Materials and APS consume approved definitions; they do not own imported BOM/routing masters.


## G2.7 implemented assimilation boundary

The executable boundary now distinguishes two source contracts:

1. `COMPLETE_ARTICLE_STRUCTURE`
   - immutable source-row staging;
   - exactly-one-FIN validation;
   - FIN flattened requirement projection;
   - non-FIN SourceOperationState evidence;
   - Article discovery/upsert;
   - UoM alias discovery/review;
   - reconciliation oracle only.

2. `DIRECT_ARTICLE_STRUCTURE`
   - immutable parent→child relation staging;
   - reachability, duplicate and cycle validation;
   - content-addressed ArticleRevision candidates;
   - DRAFT BOMRevision/BOMComponent candidates;
   - no automatic publication.

The complete report never fabricates recursive hierarchy. Only a source that preserves direct parent-child relations can author candidate BOM edges.

Reconciliation compares the candidate recursive explosion against the validated complete-report FIN projection. Blocking DQ prevents canonical application; warnings remain visible and can yield MATCH_WITH_WARNINGS.

The public repository contains only non-proprietary derived corpus metadata for X-1148, X-1149, X-2209, X-6111 and X-7070. Raw FAIC PDFs remain outside the repository.
