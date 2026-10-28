# ADR-0017 — Backup, Restore and Retention Baseline

Status: Accepted  
Date: 2026-10-28

## Decision
Production deployment must have tested backups before entering Parallel/Production stages.

Baseline objectives:
- database backups automated;
- backup copies separated from the live database volume;
- application configuration and controlled document/import metadata backed up;
- restore procedure documented and tested;
- restore evidence retained.

## Database strategy
Preferred PostgreSQL production strategy:
- regular full/base backups;
- WAL archiving or equivalent point-in-time recovery mechanism when production criticality warrants it;
- encrypted backup storage;
- integrity checks.

## Initial service objectives
Reference targets:
- RPO: <= 24 h during early pilot/shadow stage;
- RPO: <= 1 h before production release;
- RTO: <= 4 h before production release.

These are architecture targets and must be validated against FAIC infrastructure before G13.

## Reference retention
Initial policy:
- 7 daily restore points;
- 4 weekly restore points;
- 12 monthly restore points.

Retention is configurable and may be increased for legal/operational requirements.

## Restore rule
A backup policy is not considered operational until a restore test succeeds.

At minimum:
1. provision clean target;
2. restore database;
3. restore configuration/required controlled files;
4. start application;
5. run health checks;
6. verify representative records;
7. record evidence.

## Scope boundary
This does not back up Tango or Prolowin; each external system remains responsible for its own persistence.
