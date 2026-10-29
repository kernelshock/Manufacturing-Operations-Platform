# Database migrations

Alembic owns the PostgreSQL schema migration history for MOP.

Rules:
- never edit an applied migration in place;
- create a new revision for every schema change;
- test migrations against a clean PostgreSQL database;
- G1.2 establishes the baseline revision only; business tables begin in later G1 slices.
