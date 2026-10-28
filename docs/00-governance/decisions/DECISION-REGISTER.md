# Decision Register

| ID | Decision | Status | ADR | Date | Notes |
|---|---|---|---|---|---|
| DEC-001 | Use a modular monolith as the initial runtime architecture | ACCEPTED | ADR-0001 | 2026-10-27 | Avoid premature microservices while preserving extraction boundaries |
| DEC-002 | Adopt API-first and event-oriented module contracts | ACCEPTED | ADR-0002 | 2026-10-27 | Enables decoupling and future integrations |
| DEC-003 | Treat FAIC v1.4 as functional reference, not production foundation | ACCEPTED | ADR-0003 | 2026-10-27 | Requirements source and behavioral reference |
| DEC-004 | Use stage-gate releases with documented tests/evidence | ACCEPTED | ADR-0004 | 2026-10-27 | No gate release without validation |
| DEC-005 | Prolowin is the operational purchasing/reference system, but not FAIC's production stock System of Record; Tango owns the formal accounting document chain | ACCEPTED | ADR-0005 | 2026-10-27 | Operational stock source remains open |
| DEC-006 | Initial Prolowin integration uses controlled CSV/XLSX exports and report-derived files; API remains optional pending vendor verification | ACCEPTED | ADR-0006 | 2026-10-27 | Avoids blocking platform design on an unverified API |
| DEC-007 | Python/FastAPI backend, PostgreSQL, React/TypeScript frontend, REST/OpenAPI and transactional outbox baseline | ACCEPTED | ADR-0014 | 2026-10-28 | Exact dependency versions pinned during G1 |
| DEC-008 | Initial deployment uses on-premise/intranet Linux host or VM with Docker Compose and browser clients | ACCEPTED | ADR-0015 | 2026-10-28 | Validate actual host sizing before pilot |
| DEC-009 | Initial application-local identity + RBAC with future OIDC federation boundary | ACCEPTED | ADR-0016 | 2026-10-28 | Avoid blocking G1 on unknown corporate identity infrastructure |

| DEC-010 | Initial operational inventory truth is the physical point-of-use Kanban container/card state; MOP will digitize Kanban state before attempting exact perpetual stock | ACCEPTED | ADR-0007 | 2026-10-27 | Exact stock ledger is a later maturity step, not a prerequisite for first deployment |

| DEC-011 | Legacy PP/PR workbook values are historical reference only and require recalculation from current demand/lead-time inputs | ACCEPTED | ADR-0008 | 2026-10-27 | Preserve method knowledge, not stale numeric outputs |

| DEC-012 | Existing Kanban PP/PR values and historical supplier-performance/lead-time data are non-verifiable and cannot be used as calibrated inputs | ACCEPTED | ADR-0009 | 2026-10-27 | New baseline must be measured prospectively |

| DEC-013 | Weekly production plans and issued taquillas are the trusted near-term demand source for Materials/APS recalibration | ACCEPTED | ADR-0010 | 2026-10-27 | Use as primary demand signal for projected material exposure |

| DEC-014 | BOM/ABM and BOP/Routing are separate canonical structures linked by Article/ProductRevision | ACCEPTED | ADR-0011 | 2026-10-28 | Prevent material-demand and process-routing semantics from being conflated |

| DEC-015 | For validated Prolowin complete-structure reports, FIN rows form the flattened quantity projection; non-FIN rows are routing evidence and the root FIN is excluded from demand | ACCEPTED | ADR-0012 | 2026-10-28 | Guarded by import validation; recursive BOM still comes from native parent-child structure |

| DEC-016 | Master Data is the sole canonical owner of Article/Revision/BOM/Routing manufacturing definitions | ACCEPTED | ADR-0013 | 2026-10-28 | Materials and APS consume approved definitions; no duplicate domain truth |

| DEC-017 | Proprietary FAIC source PDFs and equivalent raw manufacturing evidence are not committed to the public GitHub repository | ACCEPTED | Governance data boundary | 2026-10-28 | Store hashes/derived non-sensitive architecture evidence only unless repository visibility changes and access is approved |

| DEC-018 | Automated PostgreSQL backup/restore baseline with tested recovery and configurable retention | ACCEPTED | ADR-0017 | 2026-10-28 | Production targets RPO <=1h and RTO <=4h subject to infrastructure validation |

| DEC-019 | First release is single-tenant per deployment with explicit multi-plant domain model | ACCEPTED | ADR-0018 | 2026-10-28 | Shared SaaS multi-tenancy deferred |

| DEC-020 | Exact perpetual stock maturity is deferred to G6/G7; initial material truth remains physical/e-Kanban state | ACCEPTED | ADR-0007 | 2026-10-28 | Not a G0 blocker |

| DEC-021 | Prolowin API verification is deferred to G11 and remains non-blocking because file integration is accepted | DEFERRED | ADR-0006 / Issue #2 | 2026-10-28 | Revisit if vendor-supported API becomes available |
