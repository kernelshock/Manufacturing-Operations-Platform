# Material Demand Derivation from Plan and Taquilla

Status: G0 requirement  
Date: 2026-10-27

## Trusted operational inputs
- Weekly production plan
- Issued taquilla
- Product / variant / width / configuration
- Quantity
- Effective ABM/BOM

## Required derivation

For each planned product quantity:

```text
Material requirement =
Planned product quantity
×
Material quantity in effective ABM/BOM
```

Requirements are then aggregated by:
- material;
- replenishment loop;
- time horizon;
- productive area where relevant.

## Required traceability
Every projected material requirement must be traceable back to:
- plan;
- taquilla;
- product;
- product variant/configuration;
- ABM/BOM revision;
- quantity;
- replenishment loop.

## Rule
No PP/PR proposal may use an opaque demand number. The user must be able to drill from:

```text
Proposed material demand
    ↓
Plan
    ↓
Taquilla
    ↓
Product
    ↓
ABM/BOM line
```

## Migration objective
Replace historical, manually maintained demand assumptions with current production demand derived from real released work.
