# ADR-0006 — Initial Prolowin Integration via Controlled File Exchange

Status: Accepted  
Date: 2026-10-27

## Context
FAIC confirms that Prolowin is operational for:
- articles/materials;
- stock;
- suppliers;
- purchase orders;
- receipts.

Current practical access is through:
- table export to Excel;
- table export to CSV;
- queries from the Prolowin user interface;
- generated reports.

A supported public API has not been confirmed.

## Decision
The initial Prolowin adapter will use controlled file-based ingestion, prioritizing CSV and XLSX exports.

The architecture must keep the adapter boundary independent from the source mechanism so a future API or database connector can replace file ingestion without changing Materials, Purchasing, APS or Intelligence domain logic.

## Ingestion principles
1. Preserve Prolowin article/supplier/order identifiers as external business keys.
2. Keep source filename, import timestamp, source hash and mapping version.
3. Validate required columns and units before accepting a batch.
4. Make imports idempotent where stable source keys exist.
5. Store rejected rows with reason; never silently discard.
6. Separate staging/import data from canonical domain data.
7. Reconciliation must expose source vs platform discrepancies.
8. No write-back to Prolowin is authorized by this ADR.

## API investigation
Public web research on 2026-10-27 did not identify reliable public documentation for an API belonging to the specific Prolowin system used by FAIC. Search results for similarly named products are not sufficient evidence.

API availability must therefore be verified with:
- Prolowin vendor/support;
- installed-version documentation;
- license/contract information;
- application administration/configuration.

## Consequences
File exchange becomes the supported G0/G1 integration baseline. API support, if later confirmed, will be introduced through a separate adapter and ADR.
