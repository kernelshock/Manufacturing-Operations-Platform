# ADR-0010 — Weekly Plans and Taquillas as Trusted Near-term Demand Source

Status: Accepted  
Date: 2026-10-27

## Context
FAIC confirms that:
- weekly production plans are highly reliable;
- issued production taquillas are highly reliable.

Historical demand forecasts used in the legacy reorder-point workbook are not considered current or sufficiently traceable.

## Decision
For near-term material planning and PP/PR recalibration, the Manufacturing Operations Platform will treat the following as the primary trusted demand source:

1. released/approved weekly production plans;
2. issued taquillas associated with those plans.

These sources will be translated into material demand through the applicable Product + Variant + ABM/BOM relationships.

## Demand chain

```text
WEEKLY PRODUCTION PLAN
        |
        v
TAQUILLAS
        |
        v
PRODUCT / VARIANT / QUANTITY
        |
        v
ABM / BOM
        |
        v
MATERIAL DEMAND
        |
        v
REPLENISHMENT LOOP DEMAND
        |
        v
PROJECTED KANBAN RISK / PP-PR ANALYSIS
```

## Aggregation rule
If the same material is consumed by multiple products or areas linked to the same replenishment loop, material demand is aggregated before comparing against the Kanban/replenishment policy.

## Confidence hierarchy
Initial demand hierarchy:

```text
1. Issued taquilla / released weekly plan        -> HIGH confidence
2. Approved but not yet released internal plan   -> MEDIUM, if later introduced
3. Commercial forecast / historical expectation  -> advisory only until validated
```

## Consequences
- G2/G3 importers must preserve plan/taquilla traceability.
- ABM/BOM version/effectivity becomes critical.
- Materials can calculate upcoming demand from actual planned production.
- APS and Materials must use the same canonical demand source to avoid contradictory calculations.
- Legacy demand figures from the old PP workbook are not used as the primary driver.
