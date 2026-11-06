# G6 — Code Release Record

**Release scope:** Source code only, G6.1–G6.8 Materials.  
**Approval:** User explicitly directed final review, controlled merge of PR #14 and formal G6/G7 handoff in the conversation on 2026-11-05 (America/Argentina/Cordoba).  
**Merged PR:** [#14](https://github.com/kernelshock/Manufacturing-Operations-Platform/pull/14).  
**Source head reviewed and merged:** `9f20de40251645bd2dfceeaacc3325ebab7c91d3`.  
**Merge commit on `main`:** `b52b3b9e748f4e4b846df16199510733338f2046`.  
**GitHub merged timestamp:** 2026-11-06 01:45:02 UTC.  
**Decision:** **G6 CODE RELEASED TO MAIN**. **FAIC PRODUCTION DEPLOYMENT NOT AUTHORIZED**.

## Verification basis

- Previous G6.8 integrated gate: tested `8056dcc287b27c1cf19b39395198740d6cc8ce7f` on zrtserver, PASS for disposable PostgreSQL, forward/reverse migrations, G0–G6 backend, security/supply chain, frontend, real Chrome runtime and synthetic material projection.
- GitHub Actions G6 Materials run [42136591321](https://github.com/kernelshock/Manufacturing-Operations-Platform/actions/runs/42136591321) PASS on that same code commit, 202 backend tests passed, G4 regression 2 passed, browser Materials and read-only stock invariants passed.
- Subsequent documentation update `9faadd3c6df5a431d7823b43ef9b828fb4537ed7` passed GitHub Actions [42142556848](https://github.com/kernelshock/Manufacturing-Operations-Platform/actions/runs/42142556848).
- At final PR review, Codex identified three P2 issues: visibility of all transcribed fields to independent procurement reviewers; historical purchase-order summary incorrectly including future evidence after `as_of`; invalid zero non-opening stock movements incorrectly producing a server error.
- All three were corrected in the feature branch; regression assertions were added for historical evidence cutoffs and invalid zero stock movements.
- Final reviewed head `9f20de40251645bd2dfceeaacc3325ebab7c91d3` passed G6 Materials GitHub Actions [42145367783](https://github.com/kernelshock/Manufacturing-Operations-Platform/actions/runs/42145367783), with `g6-domain`, `g6-frontend`, `g6-runtime` and `g6-gate` SUCCESS before merge.
- GitHub accepted an ordinary merge commit with `expected_head_sha` set to that precise tested head. PR #14 is CLOSED / MERGED; `main` was directly verified at `b52b3b9e748f4e4b846df16199510733338f2046`.

## Conditions and exclusions

1. This is a source-code integration/release milestone only. No migration or write occurred on any FAIC production DB; no Prolowin production import, real inventory posting, supplier order or production change was authorized or executed.
2. Real operational installation, backups/restore, LAN access, user/role configuration, real BOM/warehouse openings and data-owner UAT remain separately gated.
3. Any post-merge workflows on `main` are additional confirmation and should be recorded with their actual results; do not claim they finished before checking.
4. No live purchasing automation exists under G6. G7 requirements include supplier reliability, promised-vs-actual delivery, partial receipts, business-day calendar lead times, safety stock, reorder point (PP), replenishment quantity (CR), reservations and risk handling. No assumptions of Prolowin API access or complete export data.
5. Local zrtserver `main` synchronization is **user-initiated and not yet attested** by this release record; it must be fast-forward-only after checking a clean working tree.

## Next controlled milestone

G7 — Materials Planning / Procurement Intelligence, on a separate feature branch based on the released G6 `main`. First gate: **G7.1 — Scope, Decision Policies & Acceptance Contracts**. No automatic purchasing or live deployment in G7.1.

**Rollback reference:** pre-G6 `main` = `779dfac01c2b64f17120f56119a991865c67be67`. Preserve merged history; any rollback requires a governed revert/migration plan, not database reset.
