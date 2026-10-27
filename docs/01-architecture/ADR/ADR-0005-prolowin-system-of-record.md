# ADR-0005 — Prolowin as Authoritative Source for Materials and Purchasing

Status: Accepted  
Date: 2026-10-27

## Context
FAIC currently manages the following operational domains in Prolowin:
- articles/materials;
- stock;
- suppliers;
- purchase orders;
- receipts.

The new Manufacturing Operations Platform needs these domains to calculate material availability, APS constraints, reorder points, replenishment quantities, supplier lead-time exposure and purchasing status.

## Decision
Prolowin is the authoritative System of Record for the five confirmed domains.

The Manufacturing Operations Platform will initially:
1. consume and normalize Prolowin data into the canonical model;
2. reconcile operational material/purchasing views against Prolowin;
3. avoid assuming write authority over those domains;
4. keep platform-generated calculations (for example PP/PR, projected shortages, Kanban signals and risk to production plans) as operational decision-support data unless a later integration decision explicitly authorizes write-back.

## Open technical decision
The supported access mechanism is not yet defined. G0 must determine whether integration will use:
- database/read-only SQL;
- API;
- scheduled exports;
- CSV/XLSX/TXT;
- reports;
- another supported mechanism.

## Consequences
- Prolowin data identifiers must be preserved as external/business keys.
- The platform requires reconciliation/audit metadata for imported records.
- Materials/Purchasing cannot be finalized until access cadence and data freshness are known.
- Write-back must be a separate explicit ADR.
