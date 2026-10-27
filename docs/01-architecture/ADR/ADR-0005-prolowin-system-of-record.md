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
Prolowin is **not** the authoritative stock system for FAIC's production operations.

Its confirmed role is the operational purchasing reference for:
- purchase orders;
- supplier/material information;
- supplier delay/reclaim follow-up.

Prolowin may expose stock functionality, but FAIC does not currently use that capability as production stock truth.

Tango is the authoritative external system for the formal economic/accounting document chain (including remittances, invoices and payments). That accounting scope is explicitly excluded from the current platform phase.

The Manufacturing Operations Platform will initially:
1. consume and normalize Prolowin purchasing/reference data;
2. preserve Tango as an external accounting boundary;
3. avoid write-back to either system unless separately approved;
4. keep PP/PR, projected shortages, Kanban signals and production-risk calculations inside the operational platform;
5. define a separate authoritative source/ledger for **physical operational stock** before Materials can be released.

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
