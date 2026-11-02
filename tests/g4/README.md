# G4 APS tests

G4.1 through G4.7 cover scheduling identity/lifecycle, deterministic demand expansion, calendar/capacity projection, finite-capacity sequencing, publication/supersession, read-only Gantt projection and isolated what-if evaluation.

G4.8 adds an explicit gate-hardening contract that verifies:
- recorded completion of G4.1–G4.7;
- APS/MES and future-gate ownership boundaries;
- server-side aps.read / aps.edit authorization boundaries;
- audit actions for every APS mutation surface;
- immutable CURRENT/SUPERSEDED publication invariants;
- deterministic solver ordering/tie-breaking;
- idempotent replay guards;
- what-if isolation and explicit application;
- Gantt read-only ownership;
- exclusion of G5/G6/G7/G8/G9 authoritative state from G4 persistence.
