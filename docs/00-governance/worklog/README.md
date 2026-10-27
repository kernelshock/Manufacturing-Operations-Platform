# Development Worklog

The worklog records actual development effort by gate and module.

## Required fields
- date
- gate
- module
- task
- category
- actual_hours
- result
- evidence
- rework
- rework_reason
- status

## Categories
ANALYSIS, ARCHITECTURE, UX, DEVELOPMENT, DATA, TEST, DOCUMENTATION, DEPLOYMENT, REWORK.

## Rule
`actual_hours` must contain measured effort. If the value has not yet been measured/confirmed, leave it blank. Do not backfill estimates as if they were actual hours.

## Direction reporting
The worklog will support:
- cumulative hours;
- hours per module;
- hours per gate;
- rework hours;
- evidence per activity;
- completed vs open tasks.
