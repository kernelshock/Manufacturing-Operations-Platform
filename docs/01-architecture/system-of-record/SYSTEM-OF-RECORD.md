# System of Record Matrix — Draft

Status: Requires G0 confirmation with FAIC.

| Data domain | Proposed authoritative source | Platform role | Status |
|---|---|---|---|
| Production plan | Operations Platform | Master | provisional |
| Taquilla / production-order detail | PCP / Operations Platform | Master after controlled import | provisional |
| Product manufacturing definition | Engineering / controlled ABM sources | Reconciled master | provisional |
| Operational stock | OPEN — Prolowin capability exists but is not used operationally at FAIC | Source to be defined; platform may need its own operational stock ledger | OPEN |
| Accounting / financial documents | Tango | External master; outside current project scope | confirmed boundary |
| Suppliers | Prolowin | Mirror/reconcile | confirmed |
| Purchase orders / purchasing follow-up | Prolowin | Operational purchasing reference and supplier-delay follow-up | confirmed |
| Remittances / invoices / payments | Tango | External accounting/commercial record; excluded from current scope | confirmed boundary |
| Production execution | MES | Master | proposed |
| Maintenance execution | Maintenance module | Master | proposed |
| Workforce operational availability | Workforce | Operational master | proposed |
| Payroll / personnel legal data | HR system | External master | proposed |
| Costs/accounting | Accounting system | External master | proposed |

## G0 blocking question
Confirm how FAIC currently stores and exposes:
- article/material master;
- stock;
- suppliers;
- purchase orders;
- receipts;
- employee/shift information.

For Prolowin, determine whether access is available through database, API, scheduled export, CSV/XLSX or other controlled mechanism.
