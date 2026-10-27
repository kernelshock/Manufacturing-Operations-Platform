# Module Responsibility Map

| Module | Owns | Does not own |
|---|---|---|
| Core | identity, roles, permissions, configuration, audit, common infrastructure | production domain decisions |
| Master Data | products, revisions, materials, resources, suppliers, calendars | production execution |
| Demand / Orders | orders, plans, taquillas, priorities | finite scheduling |
| APS | schedule proposals/publications, constraints, capacity | execution truth |
| MES | actual operation execution and transfers | master product definition |
| Materials | BOM/ABM consumption model, inventory, movements, PP/PR, Kanban signals | commercial purchasing approval |
| Purchasing | purchase requests/orders, supplier delivery commitments, receipts | inventory consumption logic |
| Maintenance | assets, failures, work orders, downtime | production schedule ownership |
| Workforce | shifts, skills, availability, assignments, labor time | HR payroll |
| Intelligence | KPIs, targets, trends, executive reporting, actions | transactional source data |
| Integration Hub | adapters, mapping, synchronization contracts | domain ownership |

## Boundary rule
A module may query another module only through an approved contract or read model. Direct access to another module's internal tables is prohibited.
