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
