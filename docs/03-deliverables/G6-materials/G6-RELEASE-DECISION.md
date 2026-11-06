# G6 — Formal Release Decision Package (proposed)

**Project:** FAIC Manufacturing Operations Platform (MOP)  
**Gate:** G6 Materials (G6.1–G6.8)  
**Prepared:** 2026-11-06 UTC  
**Governance status:** **READY FOR RELEASE DECISION — NOT RELEASED**  
**Release candidate code SHA:** `8056dcc287b27c1cf19b39395198740d6cc8ce7f`  
**PR:** [#14 — feat/G6-materials](https://github.com/kernelshock/Manufacturing-Operations-Platform/pull/14), currently OPEN / DRAFT / UNMERGED  
**Evidence:** [G6.8-EVIDENCE.md](G6.8-EVIDENCE.md) and [GitHub Actions run 42136591321](https://github.com/kernelshock/Manufacturing-Operations-Platform/actions/runs/42136591321)

## 1. Proposed resolution

> **Proposed resolution G6-RC-01:** Accept G6.8 as technically completed for the configured acceptance scope on code SHA `8056dcc`. Recommend formal release of G6 to the governed code baseline **subject to the release sign-offs below**. Do not interpret technical acceptance as production-data readiness, approval to post physical stock, authorization to purchase, or permission to deploy to FAIC production. PR #14 stays DRAFT until explicit authorization to mark ready and merge.

**Current decision:** NOT SIGNED. **Merge:** NOT AUTHORIZED. **Production deployment:** NOT AUTHORIZED.

The user has authorized use of **an isolated validation deployment** for continuation of testing. This is not an authorization for production rollout or an explicit merge instruction.

## 2. Technical acceptance already verified

| Release item | Verified result | Evidence |
| --- | --- | --- |
| Local isolated G6.8 acceptance | All configured local stages PASS at exact code SHA | zrtserver terminal output, evidence `runtime-data/g68/20261106T002540Z-8056dcc28-14821` |
| GitHub Actions | `G6 Materials` run 42136591321 SUCCESS, same SHA | GitHub Actions API |
| Backend G0–G6 regression | 202 passed, no skips reported | `g6-domain` decoded job log |
| Historical G4 recheck | 2 passed | `g6-domain` decoded job log |
| Migrations and schema | forward, downgrade, replay, check PASS | local gate and CI |
| Frontend | audit, TypeScript, unit tests and build PASS | `g6-frontend` |
| Runtime + MES | Chrome/FastAPI/PostgreSQL smoke PASS | `g6-runtime` |
| Materials data-bearing browser | synthetic mixed taquillas, BOM, holds, UNKNOWN, plant/plan projection PASS | `g6-runtime` decoded log |
| Read-only stock/holds invariant | PASS | `g6-runtime` decoded log |
| Supply chain | secrets, package checks, dependency audit PASS | local gate and CI |

## 3. Functional scope to release

- G6.1 inventory structures and location-based physical ledger; unknown quantities must remain unknown.
- G6.2 traceable physical movement posting subject to existing application rules and permissions.
- G6.3 theoretical BOM-derived demand by plan and taquilla and date-effective revisions.
- G6.4 explicit MES measured consumption without automatic assumptions about theoretical issue.
- G6.5 governed reservation / release and site-specific availability without implying quality release.
- G6.6 Prolowin legacy procurement **manual/screenshot evidence** and independent review, explicitly non-stock-posting and incomplete until captured.
- G6.7 plan/plant materials projection and frontend dashboard: source isolation and indicative deficits only.
- G6.8 test hardening, local/CI checks and data-bearing browser regression.

## 4. Exclusions / unresolved operational dependencies

- No ATP, automatic purchase orders, automatic supplier selection, or time-phased purchasing decisions; G7 is separately scoped.
- No assertion that all FAIC Prolowin data have been ingested. Export limitations and screenshot-based capture remain explicit.
- No assumption that material or warehouse opening balances for FAIC production are accurate or fully initialized.
- No claim that UI export/print and each Prolowin reviewer screen were independently covered by data-bearing browser tests; this is an enhancement/operational UAT topic.
- No production readiness claim for backups, disaster recovery, user provisioning, LAN access, role-permission mapping, or concurrency of multiple operational users based exclusively on synthetic CI.
- No permission for direct production database migration or physical movements without separate change approval.

## 5. Mandatory authorization checklist

| Item | Owner / evidence to record | Status |
| --- | --- | --- |
| G6.8 technical validation | Engineering / G6.8-EVIDENCE.md | **ACCEPTED (test scope)** |
| Source freeze for release | Technical reviewer / tested SHA and PR diff | **PENDING** |
| Peer review / security and interface assumptions | Technical reviewer / sign-off | **PENDING** |
| Review local screenshot and test logs | Engineering / attachment and checksum | **PENDING** |
| Intended target defined (code baseline, local dev, staging or production) | Release authority / change record | **PENDING** |
| Backups, migration dry-run and recovery test for intended environment | Infrastructure owner / evidence | **PENDING IF DEPLOYING** |
| Actual FAIC role permissions, network and data-owner acceptance | FAIC owners / UAT | **PENDING IF DEPLOYING** |
| Explicit PR #14 merge and release approval | Authorized decision maker / written instruction | **PENDING** |
| Post-merge smoke, release tag and rollback reference | Engineering / release record | **NOT STARTED** |

## 6. Decision record to complete

- **Decision identifier:** G6-RC-01
- **Decision maker / role:** [to be recorded]
- **Decision date/time:** [to be recorded]
- **Approved action:** [ ] Close technical gate only; [ ] Approve PR #14 merge into main; [ ] Approve staging deployment; [ ] Approve production deployment (separate production change record required).
- **Approved code SHA:** `8056dcc287b27c1cf19b39395198740d6cc8ce7f` (or an explicitly revalidated newer code SHA)
- **Target host / environment:** [to be recorded]
- **Reviewed evidence and exceptions:** [to be recorded]
- **Backup/rollback decision:** [to be recorded]
- **Signature / approval reference:** [to be recorded]

## 7. Controlled execution after the decision

1. Confirm approved action, review current PR diff and freeze the exact release candidate. If code changes, obtain same-SHA acceptance again.
2. Ensure the PR has successful required checks, is not blocked, and receives explicit authorization before changing its DRAFT status or merging.
3. Merge to `main` only with approval, record merge SHA, then tag and synchronize the chosen environment using the safe local checkpoint.
4. Run relevant smoke tests on the integrated baseline; preserve logs, rollback reference and formal release changelog.
5. Authorize any production data migration and role activation under a **separate** rollout plan. No Prolowin data or FAIC stock can be inferred from synthetic test fixtures.

**Formal release decision is prepared, not executed.**
