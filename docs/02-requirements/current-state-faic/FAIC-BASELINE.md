# FAIC Current-state Baseline

This document captures validated operational knowledge that the new architecture must preserve during migration.

## Production flow baseline
BALANCINES → SOLDADURA → PINTURA / intermediate treatment where applicable → CORTE TELA → COSTURA → PEGADO → ENFUNDADO → ARMADO → LOGÍSTICA

Actual routing is configurable and may branch or skip processes.

Important distinctions:
- wooden bases may route from Balancines to Pegado;
- metallic bases route through Soldadura;
- plastics feed Armado;
- apoyapiernas and apoyapiés are separate manufacturing concepts;
- apoyapiés are cut and welded, then integrated into the chassis before leaving welding;
- repairs may use non-standard routes, including repeated processes.

## Planning unit
Plan → one or more taquillas → one or more products/configurations per taquilla.

Double-decker vehicles may be represented by one or two source documents and must consolidate into one logical taquilla.

## Calendar baseline
- Monday–Thursday 07:00–16:00
- Friday 07:00–15:00
- lunch 12:00–12:30
- continuity across taquillas

## Existing validated concepts
- finite capacity and process Gantt;
- variable Gantt resolution;
- setup;
- real vs planned;
- material restrictions;
- visual route editor;
- product/width/configuration intelligence;
- maintenance impact on production;
- ABM/BOM-driven material consumption;
- PP/PR and supplier lead time;
- purchasing and receipt linkage;
- workforce as an operational resource;
- executive weekly/monthly reporting.

The new platform must introduce better discipline without abruptly changing FAIC operating logic.
