# G7 — Materials Planning & Procurement Intelligence

**Initiation:** 2026-11-06 UTC.  
**Status:** OPEN / PLANNING ONLY; no operational purchasing or production deployment.  
**Branch:** `feat/G7-materials-planning`.  
**Baseline:** Released G6 on `main`, PR #14 merged at `b52b3b9e748f4e4b846df16199510733338f2046`; code-release evidence in `docs/03-deliverables/G6-materials/G6-RELEASE-RECORD.md`.

## Mission

Transform verifiable G2 BOM, G3 demand/taquillas, G4 finite-capacity schedules, G5 execution, G6 immutable physical ledger/reservations/actual usage and partial manually verified Prolowin procurement records into **explainable materials planning and supplier-risk recommendations**, without falsely presenting missing data as zero or autonomously issuing purchase orders.

## Non-negotiable boundaries

- Explicit distinction: **physical on-hand**, **quality-released usable**, **reserved**, **consumed**, **open purchase order**, **supplier-promised inbound**, **verified receipt**, and **unconfirmed Prolowin history**. No provisional event is automatic stock.
- Maintain exact Decimal arithmetic and canonical G2 article/UoM; preserve source line, BOM version, taquilla, location, date and user lineage.
- Reorder point (`P.P.`) and replenishment quantity (`C.R.`) must be explainable, reviewable and adjustable by role. Existing 25% safety factor is a **configurable policy baseline**, not evidence of vendor reliability or a fixed universal optimum.
- Lead times use the **FAIC agreed business-day calendar**, not raw calendar days; original supplier promise remains immutable, revised commitments remain separate, partial receipts/claims and production-risk escalations are first-class facts.
- Prolowin remains legacy/closed; support manual screenshot transcription with independent verification. Excel/CSV weekly exports are optional secondary reconciliation and do not imply complete supplier history. Prohibit fabricated ERP fields or silent API assumptions.
- PP/CR forecasts, supplier alternatives and purchase proposals are recommendations, not automatic POs, commitments or ERP writes.
- Isolation by plant, scoped access, audit trail, no inventory mutation on projection and no accidental cross-plan stock reuse.
- No FAIC live data, migrations, purchasing actions, role provisioning or production network deployment without separate explicit authorization.

## Proposed execution gates

| Gate | Objective | Release evidence |
| --- | --- | --- |
| **G7.1 — Scope, Decision Policies & Acceptance Contracts** | Define terms (PP/CR, calendar, lead time, service level, stock policy), roles, data completeness and fail-closed statuses; map G6 outputs into projections | Approved decision catalog and executable synthetic acceptance cases |
| **G7.2 — Supply & Inventory Position** | Material/location/plant time-phased positions distinguishing physical, held, quality status and explicit incoming POs | Deterministic Decimal unit and PostgreSQL tests, unknown semantics |
| **G7.3 — Lead-Time & Supplier Reliability** | Reconcile original/revised promised dates, actual partial receipts, claims and business-day delivery variability | Supplier evidence coverage and confidence indicators, historical as-of tests |
| **G7.4 — Reorder Point & Safety Stock Policy** | PP with consumption per seat/product and shared articles, lead-time variability, service-level and optional 25% safety policy | Comparative formula tests, sensitivity analysis, provenance and overrides |
| **G7.5 — Replenishment Quantity & Scenario Planning** | Fixed and calculated CR, packaging/minimums where verified, demand horizon, alternate suppliers and shortage simulations | Recommendation-only scenarios with permissions and review trail |
| **G7.6 — Exception Management / Governance** | Risk to production, critical shortage, alternate-supplier evaluation, review/approve/reject decision | Role separation, audit, no auto supplier switch or PO |
| **G7.7 — Dashboard, Reporting & Integration** | Executive and operating dashboards, filtered cards, CSV/PDF or printable reports, Prolowin-assisted capture | User-visible scenarios with synthetic data, accurate labels and exports |
| **G7.8 — Gate Hardening & Release Decision** | Full G0–G7 regression, migrations, dependency audit, Chrome/live API, same-SHA CI and review | Evidence matrix and explicit gate authorization |

This ordering is an initiation proposal and is not permission to implement or deploy beyond G7.1 until each increment is accepted.

## G7.1 decisions to formalize first

1. Business-day definition per supplier and plant, public holidays, operating shifts and lead-time clock start (PO acceptance vs issue).
2. Consumption basis: historical per product, per seat, or both; allocate materials shared by one or more product families without double counting.
3. Stock quantity policy: zero initialized physical stock vs missing UNKNOWN; Quality-usable stock requires actual Quality evidence, not an inferred boolean.
4. Planning horizon, safety-stock model and circumstances where missing supplier history prevents statistical inference; produce confidence/coverage status.
5. Choice of `C.R.`: fixed quantity vs calculated quantity, verified supplier MOQ/pack/multiples only when available.
6. Mandatory authority and audit for updating policy parameters, reviewing sourcing alternatives and approving suggestions; never auto-create PO.
7. Expected integration path from G6: only verified facts with partial-history warning; no unverified manual capture or vendor promise promoted to physical stock.
8. Acceptance cases: zero initial stock, unknown stock, shared material across products, two taquillas, late partial receipt, revised promised date, no API access, underreported manual history, and a production-risk escalation.

## Status at opening

**G7 OPEN (documentation and architecture planning).** No executable G7 materials planning code, migrations or automatic purchasing functions are claimed. G6 `main` stays governed. Next concrete increment: G7.1 policy/contract specification and synthetic deterministic cases before implementation.
