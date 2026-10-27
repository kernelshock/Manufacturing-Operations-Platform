# Module Responsibility Map

| Module | Owns | Does not own |
|---|---|---|
| Core | identity, roles, permissions, configuration, audit, common infrastructure | production domain decisions |
| Master Data | products, revisions, materials, resources, suppliers, calendars | production execution |
| Demand / Orders | orders, plans, taquillas, priorities | finite scheduling |
| APS | schedule proposals/publications, constraints, capacity | execution truth |
| MES | actual operation execution and transfers | master product definition |
| Materials | BOM/ABM consumption model, point-of-use containers, physical/e-Kanban state, projected availability, PP/PR and material movements | commercial purchasing approval and accounting |
| Purchasing | replenishment requests, purchase-order references, supplier commitments and receiving workflow | production consumption logic and accounting documents |
| Maintenance | assets, failures, work orders, downtime | production schedule ownership |
| Workforce | shifts, skills, availability, assignments, labor time | HR payroll |
| Intelligence | KPIs, targets, trends, executive reporting, actions | transactional source data |
| Integration Hub | adapters, mapping, synchronization contracts | domain ownership |

## Boundary rule
A module may query another module only through an approved contract or read model. Direct access to another module's internal tables is prohibited.
