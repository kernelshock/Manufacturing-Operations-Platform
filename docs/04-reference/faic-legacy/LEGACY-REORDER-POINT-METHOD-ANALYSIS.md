# Legacy Reorder Point Method — Forensic Analysis

Status: G0 historical-method analysis  
Date: 2026-10-27  
Source workbook: `Calculo de Punto de Pedido_V01_R01-MXZ.xlsx`  
Source SHA-256: `7c965690c714e243348c1855d89a95d52258fabfe49b3f7d3d5b27f76bf6ef80`

## Purpose

Preserve the logic of FAIC's historical reorder-point calculation while explicitly separating the **method** from the obsolete/broken source data that currently makes many card values unreliable.

This workbook is a historical reference and must not be treated as current operational truth.

## Workbook structure reviewed

Sheets:
- `PP`
- `DEMANDA`
- `PROVEEDORES`
- `ALMACENES PLASTICOS`
- `Hoja1`

### PP
Contains:
- material code and description;
- quantity of each material consumed per seat/model;
- weighted consumption;
- supplier;
- supplier lead time;
- safety coefficient;
- reorder point;
- observations;
- replenishment quantity.

### DEMANDA
Contains expected demand by product/model.

The workbook itself states that these values were supplied by Management from statistics and sales expectations.

No reliable date/version/effectivity metadata was found that would allow the current platform to know whether the values remain valid.

### PROVEEDORES
Contains supplier data and expected replenishment days.

The workbook note indicates that these values originate from supplier evaluations.

The table contains:
- working-day lead times;
- calendar-day lead times;
- supplier type/rubro;
- several missing or non-numeric values.

### ALMACENES PLASTICOS
Contains additional/historical reorder-point values and container information.

Many rows contain spreadsheet errors and values do not consistently reconcile with the current PP sheet or physical Kanban cards.

## Historical calculation

For the F10/model section, the workbook calculates weighted consumption using a formula equivalent to:

```text
Consumption =
Σ(Material quantity per model × Expected model demand)
-------------------------------------------------------
                         20
```

The denominator `20` is hard-coded. The workbook does not provide sufficient metadata to safely determine the business period/effectivity represented by that divisor, so it must not be reused without validation.

Supplier working-day lead time is obtained from the `PROVEEDORES` table.

The safety coefficient is assigned from lead time using a hard-coded rule similar to:

```text
lead time < 15 days       -> 1.2
lead time = 16 days       -> 1.2
lead time 15–20 days      -> 1.5
lead time >= 21 days      -> 1.7
```

Note: the explicit 16-day exception makes the historical rule internally unusual and must be reviewed rather than reproduced blindly.

The reorder point is calculated as:

```text
PP = Consumption × Working-day Lead Time × Safety Coefficient
```

## Case study — material 14027

Material:
`14027 — ALAMBRE CHICO RESPALDO MB F10 250mm`

Current workbook model-consumption inputs contributing to the calculation include:
- Moonraker +40: quantity 1 × demand 72
- Apollo: quantity 3 × demand 1492
- Soyuz Base Fija: quantity 3 × demand 139
- Skylab: quantity 1 × demand 60

Weighted source demand:

```text
72 + (3 × 1492) + (3 × 139) + 60 = 5025 units
```

Historical workbook consumption:

```text
5025 / 20 = 251.25
```

Supplier:
`ALAMBRES RUMBOS S.A.`

Historical supplier lead time:
`21 working days`

Historical safety coefficient:
`1.7`

Workbook PP:

```text
251.25 × 21 × 1.7 = 8969.625 units
```

### Contradictory values found for the same material

- Main `PP` calculation: **8969.625**
- `ALMACENES PLASTICOS` historical value: **4623.15**
- Current physical Kanban card observed in G0: **4135 units**
- Physical card replenishment quantity: **7000 units**
- Main PP sheet current replenishment quantity for 14027: blank

This is direct evidence that the method, physical card and source workbook have lost synchronization.

## Data-quality findings

The workbook contains numerous:
- `#N/A`
- `#VALUE!`
- `#NAME?`

Several formulas also contain legacy external-workbook references such as `[1]` and `[2]`, indicating broken/truncated data flows.

Other structural risks:
- supplier lead times can be blank or text values such as `IMP`, `7 O 15`, `7/15`;
- demand is not versioned/effective-dated;
- PP values coexist with manual/historical values;
- replenishment quantity is not systematically formula-driven;
- no explicit record links a physical card revision to the demand/lead-time inputs used to calculate it.

## G0 conclusion

The historical method must be preserved as **domain knowledge**, but its current values must be classified as **LEGACY / REQUIRES RECALCULATION**.

The new MOP Materials module must not import these PP/PR numbers as trusted operational parameters without revalidation.

## Requirements for the new policy

A future `ReorderPolicy` must be versioned and traceable to:
- material;
- replenishment loop;
- consuming products/areas;
- ABM/BOM revision;
- demand horizon/source;
- supplier/source;
- lead-time source and measurement window;
- safety policy;
- PP;
- replenishment quantity;
- effective-from date;
- approval;
- calculation version.

The calculation should be capable of combining:
- known APS demand in the relevant future horizon;
- historical/forecast consumption where useful;
- current supplier lead time;
- variability/safety protection;
- open replenishment/purchase status;
- container capacity;
- minimum order quantity and purchase multiple.

Exact formulas and optimization rules will be defined and validated in the Materials gate; G0 only establishes that the legacy values are not authoritative.
