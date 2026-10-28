# Prolowin Complete Structure Reference — X-6111

Status: G0 authoritative PDF sample  
Date: 2026-10-28

## Product
- Code: `X-6111`
- Family: Apollo
- Complete report: 5 pages
- Report basis: 1 finished unit

## Structural findings
The PDF confirms the same general source pattern as the Enterprise and Moonraker references:
- one FIN row per article code;
- operation-stage rows for manufactured items;
- global/shared consumables;
- high-level manufactured subassemblies;
- heterogeneous UoM.

Visible high-level modules/subassemblies include:
- `A-621` RESPALDO APOLLO R14 470 (TAPA ALTA) × 2
- `B-806` ALMOHADON SOY/APOL/DISC ... × 2
- `C-640` CHASIS APOLLO ... × 1
- `D-701` DOBLE PATA ... × 1
- `F-600` ESPUMA DE FORMA ... × 2
- `G-632` tapicería/configuration article × 2
- `SB-601`, `SC-632`, `SE-702`, `SI-800`, `SL-600(D/I)`, `SLPP-611`, `SP-605(D/I)`, `SR-606`

## Kanban reference material 14027
The report contains:
`14027 | FIN | ALAMBRE CHICO RESPALDO MB F10 | 6.0000 UNID.`

This directly links the physical Kanban card previously observed for material 14027 to an effective finished-product demand source.

For X-6111:
```text
material_14027_demand = X-6111 planned quantity × 6
```

Total replenishment-loop demand must then aggregate any additional products consuming the same material.

## Architectural use
X-6111 is the primary G0 fixture for testing:
- Kanban material linkage;
- shared component reuse across product families;
- recursive BOM explosion;
- Apollo-specific configuration handling.
