# G5 MES tests

G5.1 validates the execution-domain and dispatch foundation.

Coverage includes:
- CURRENT G4 publication as the only dispatch source;
- one dispatch identity per publication;
- immutable provenance to published APS and G2/G3 source identities;
- snapshot of planned resource/start/finish without MES actuals;
- idempotent dispatch materialization;
- DRAFT → RELEASED / CANCELLED lifecycle;
- release-time revalidation that the source publication is still CURRENT;
- mes.read / mes.edit server-side authorization contracts;
- audited create/release/cancel mutations;
- explicit exclusion of actual start/finish, produced quantity, scrap, pause/setup, operator and actual-resource state from G5.1.


G5.2 adds coverage for:
- PENDING → RUNNING → COMPLETED operation lifecycle;
- explicit START and COMPLETE events;
- actual start/finish separated from planned timestamps;
- Decimal-safe produced quantity capture;
- produced quantity differing from requested quantity without implicit scrap;
- rejection of completion before start and finish before actual start;
- idempotent replay of identical execution actions;
- conflict on attempts to rewrite completed quantity/evidence;
- continued exclusion of pause/setup/scrap/actual-resource authority.


G5.3 adds coverage for:
- optional setup start/finish before execution START;
- blocking operation START while setup remains open;
- RUNNING ↔ PAUSED lifecycle;
- repeatable interruption history with required reason codes;
- one-open-interruption database invariant;
- blocking COMPLETE while PAUSED;
- explicit actual-resource capture and mandatory deviation reason for alternate resource;
- observational start/finish/quantity/resource/setup/interruption deltas;
- continued exclusion of maintenance/workforce/material causal authority.


G5.4 adds coverage for:
- two-operation nominal-route execution;
- predecessor completion before WIP transfer;
- partial WIP transfer quantities;
- cumulative transfer bounded by predecessor produced quantity;
- explicit TRANSFERRED → RECEIVED lifecycle;
- idempotent receipt replay;
- successor START blocked until WIP is received;
- WIP incoming/outgoing/remaining trace projection;
- continued separation from G6 inventory/warehouse authority.


G5.5 covers:
- governed rework case creation and idempotent case-code replay;
- source completion and same ProductLine/dispatch boundaries;
- ordered alternative/repeated routing steps with real execution timestamps and quantities;
- explicit return to a PENDING execution operation;
- rejection of route edits after execution begins;
- isolation of rework allocation from normal WIP transfers;
- reconciliation of nominal and rework output against produced quantity;
- no G2/G3/G4 or G6/G8/G9 authority mutations.
