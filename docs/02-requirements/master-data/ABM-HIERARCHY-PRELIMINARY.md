# ABM Hierarchy — Preliminary Current-State Observation

Status: Preliminary G0 observation  
Date: 2026-10-27  
Source: FAIC costing screens supplied as examples

## What the costing screens confirm

FAIC's product structure is represented hierarchically.

At finished-product/model level, the screen shows:
- product line;
- class;
- costing date;
- Prolowin product code;
- detailed product/configuration description.

Each finished product is decomposed into ABM modules/subassemblies with:
- module name;
- module code;
- quantity;
- cost date;
- cost amount;
- certification reference/status;
- observations.

Observed module families include:
- RESPALDO
- BASE
- CHASIS
- PATA
- APOYA P.
- ESP. FORMA
- FUNDA

The display also groups modules into at least:
- `Nomenclador Estructura`
- `Nomenclador Tapicería`

## Examples observed

### Enterprise — single
Finished product code: `X-1149`
Examples of module relations:
- RESPALDO `A-115` × 1
- BASE `B-104` × 1
- CHASIS `C-110` × 1
- PATA `D-114` × 1
- APOYA P. `E-111` × 1
- ESP. FORMA `F-107` × 1
- FUNDA `G-158` × 1

### Enterprise — double
Finished product code: `X-1148`
Examples:
- RESPALDO `A-115` × 2
- BASE `B-104` × 2
- CHASIS `C-109` × 1
- PATA `D-113` × 1
- APOYA P. `E-110` × 1
- ESP. FORMA `F-107` × 2
- FUNDA `G-158` × 2

### Moonraker semicama — double
Finished product code: `X-2209`
Examples:
- RESPALDO `A-208` × 2
- BASE `B-202` × 2
- CHASIS `C-225` × 1
- PATA `D-238` × 1
- APOYA P. `E-209` × 2
- ESP. FORMA `F-207` × 2
- FUNDA `G-278` × 2

Additional examples confirm the same pattern for Discovery and Apollo.

## Architectural interpretation

These screens are sufficient to confirm a multi-level product structure:

```text
Finished Product / Configuration
        |
        +-- Structural Module / Subassembly
        |      |
        |      +-- lower-level parts/materials (to be confirmed from detailed ABM)
        |
        +-- Upholstery Module / Subassembly
               |
               +-- lower-level parts/materials (to be confirmed from detailed ABM)
```

The module codes observed here must **not yet be treated as leaf material consumption** for Materials planning.

The next detailed ABM source is required to establish:
- component/part codes below each module;
- quantity per component;
- unit of measure;
- whether quantities are per module or per finished product;
- shared components;
- revision/effectivity behavior.

## G0 requirement implication

The canonical BOM/ABM model must support **multi-level explosion**, not a flat finished-product-to-material table.

Tentative relationship:

```text
ProductRevision
  -> BOM/ABM
      -> Module/Subassembly
          -> Component / Material
```

Demand derivation for PP/PR must ultimately explode through the complete effective hierarchy before aggregating material requirements by replenishment loop.
