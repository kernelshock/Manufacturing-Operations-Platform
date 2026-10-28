# G0 Security and Operational Resilience Baseline

Status: G0 baseline
Date: 2026-10-28

## Identity
- individual user accounts;
- RBAC permissions;
- server-side authorization;
- future OIDC federation boundary.

## Network
- HTTPS for browser/API traffic;
- PostgreSQL not exposed to user workstations;
- administrative interfaces restricted;
- external imports pass through staging/validation.

## Secrets
- secrets are not committed to Git;
- environment/deployment secret injection is required;
- production environment files are excluded from source control;
- credential rotation must not require code changes.

## Audit
At minimum audit:
- login/security events;
- master-data revision approval;
- plan release/publication;
- Kanban triggers/approvals;
- purchasing approvals;
- privileged configuration changes;
- manual corrections.

## Data resilience
- database backup required;
- restore testing required;
- source import files tracked by hash;
- canonical revisions retained;
- transactional history not rewritten by later master-data changes.

## Production readiness
G13 requires:
- backup/restore evidence;
- user/role review;
- HTTPS;
- secret review;
- audit review;
- recovery procedure;
- deployment rollback procedure.
