# Decision Register

| ID | Decision | Status | ADR | Date | Notes |
|---|---|---|---|---|---|
| DEC-001 | Use a modular monolith as the initial runtime architecture | ACCEPTED | ADR-0001 | 2026-10-27 | Avoid premature microservices while preserving extraction boundaries |
| DEC-002 | Adopt API-first and event-oriented module contracts | ACCEPTED | ADR-0002 | 2026-10-27 | Enables decoupling and future integrations |
| DEC-003 | Treat FAIC v1.4 as functional reference, not production foundation | ACCEPTED | ADR-0003 | 2026-10-27 | Requirements source and behavioral reference |
| DEC-004 | Use stage-gate releases with documented tests/evidence | ACCEPTED | ADR-0004 | 2026-10-27 | No gate release without validation |
| DEC-005 | Prolowin is the operational purchasing/reference system, but not FAIC's production stock System of Record; Tango owns the formal accounting document chain | ACCEPTED | ADR-0005 | 2026-10-27 | Operational stock source remains open |
| DEC-006 | Initial Prolowin integration uses controlled CSV/XLSX exports and report-derived files; API remains optional pending vendor verification | ACCEPTED | ADR-0006 | 2026-10-27 | Avoids blocking platform design on an unverified API |
| DEC-007 | Backend/frontend technology stack | OPEN | TBD | - | To resolve in G0 |
| DEC-008 | Initial deployment topology on FAIC network | OPEN | TBD | - | Requires infrastructure inventory |
| DEC-009 | Authentication source / identity integration | OPEN | TBD | - | Requires IT context |

| DEC-010 | Initial operational inventory truth is the physical point-of-use Kanban container/card state; MOP will digitize Kanban state before attempting exact perpetual stock | ACCEPTED | ADR-0007 | 2026-10-27 | Exact stock ledger is a later maturity step, not a prerequisite for first deployment |

| DEC-011 | Legacy PP/PR workbook values are historical reference only and require recalculation from current demand/lead-time inputs | ACCEPTED | ADR-0008 | 2026-10-27 | Preserve method knowledge, not stale numeric outputs |

| DEC-012 | Existing Kanban PP/PR values and historical supplier-performance/lead-time data are non-verifiable and cannot be used as calibrated inputs | ACCEPTED | ADR-0009 | 2026-10-27 | New baseline must be measured prospectively |

| DEC-013 | Weekly production plans and issued taquillas are the trusted near-term demand source for Materials/APS recalibration | ACCEPTED | ADR-0010 | 2026-10-27 | Use as primary demand signal for projected material exposure |

| DEC-014 | BOM/ABM and BOP/Routing are separate canonical structures linked by Article/ProductRevision | ACCEPTED | ADR-0011 | 2026-10-28 | Prevent material-demand and process-routing semantics from being conflated |
