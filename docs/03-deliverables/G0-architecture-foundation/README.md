# G0 — Architecture Foundation

Status: **RELEASED**

## Purpose
Establish the architecture, governance, canonical data semantics, module boundaries, release discipline and technical decision framework before rebuilding functional modules.

## Required G0 outputs
- repository structure;
- project roadmap;
- decision register;
- architecture principles;
- canonical domain model baseline;
- initial event catalog;
- module responsibility map;
- system-of-record matrix draft;
- test/release protocol;
- worklog control;
- architecture deliverable for Direction.

## G0 exit criteria
G0 can move to VALIDATED when:
1. required repository documents exist;
2. architecture ADRs are reviewed;
3. canonical entities have ownership definitions;
4. event catalog baseline exists;
5. system-of-record questions are identified;
6. G0 structure test passes;
7. critical architecture questions are resolved or formally deferred;
8. Direction-facing G0 deliverable is generated.

G0 becomes RELEASED only after explicit approval.


## Validation evidence
- Release-gate CI: GitHub Actions run #72
- Result: SUCCESS
- Automated G0 suite: 5 passed
- Validated: 2026-10-28
- Released: 2026-10-28
- PR #1 merged to `main`
- Release merge commit: `6f79f82155789c02c8138b2caec1f617b46619db`

G0 is **RELEASED**.
