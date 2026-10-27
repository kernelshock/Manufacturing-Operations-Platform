# Contributing

## Branch policy
- `main`: released and approved baseline only.
- `feat/Gx-...`: gate or feature branches.
- `fix/...`: corrections.
- `docs/...`: documentation-only changes.

Direct development on `main` is not allowed by project convention.

## Gate workflow
Every gate follows:

1. Requirements defined.
2. Architecture/design documented.
3. Implementation completed.
4. Tests executed.
5. Evidence stored.
6. Deliverables generated.
7. Gate review completed.
8. Release decision recorded.

Gate status values:
- PLANNED
- IN PROGRESS
- VALIDATED
- RELEASED
- BLOCKED

## Commit convention
Use concise Conventional Commit-style messages where practical:
- `feat:`
- `fix:`
- `docs:`
- `test:`
- `refactor:`
- `chore:`

## Definition of Done
A change is not done only because code exists. It must include the documentation and tests needed to reproduce, understand and validate it.

## Worklog
Development effort must be recorded with actual hours. Do not replace actual effort with estimates in the historical worklog.
