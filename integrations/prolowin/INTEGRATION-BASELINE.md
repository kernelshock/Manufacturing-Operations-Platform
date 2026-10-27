# Prolowin Integration Baseline

Status: Confirmed baseline / API capability pending vendor verification  
Date: 2026-10-27

## Confirmed operational domains in Prolowin
- Articles/materials
- Stock
- Suppliers
- Purchase orders
- Receipts

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
The required synchronization frequency has not yet been defined. It must be based on the business decision latency for:
- stock availability;
- purchase status;
- receipt status;
- supplier/material updates.

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
