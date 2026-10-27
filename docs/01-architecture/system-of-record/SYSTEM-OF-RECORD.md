# System of Record Matrix — Draft

Status: Requires G0 confirmation with FAIC.

| Data domain | Proposed authoritative source | Platform role | Status |
|---|---|---|---|
| Production plan | Operations Platform | Master | provisional |
| Taquilla / production-order detail | PCP / Operations Platform | Master after controlled import | provisional |
| Product manufacturing definition | Engineering / controlled ABM sources | Reconciled master | provisional |
| Operational stock | Prolowin | External authoritative source; platform mirrors/reconciles for operations | confirmed |
| Accounting stock | Prolowin | External master | confirmed |
| Suppliers | Prolowin | Mirror/reconcile | confirmed |
| Purchase orders | Prolowin | Mirror/reconcile initially; write-back to be decided | confirmed source / integration open |
| Receipts | Prolowin | Mirror/reconcile initially; write-back to be decided | confirmed source / integration open |
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
