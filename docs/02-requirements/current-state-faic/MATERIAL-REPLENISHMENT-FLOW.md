# FAIC Current-state Material Replenishment Flow

Status: Baseline captured during G0  
Date: 2026-10-27

## Physical model
Each productive area stores its own production consumables/materials close to the point of use.

Examples may include:
- fasteners;
- fabrics, plush fabrics, leather and synthetic leather;
- plastic covers;
- armrests;
- legrests / footrests where applicable;
- USB modules / 110 V outlets;
- aisle lights;
- other coded materials contained in product ABM definitions.

Some materials are shared by several products.

## Reorder control
Containers have physical volumetric marks. The mark represents the practical reorder trigger.

```text
POINT-OF-USE CONTAINER
        |
        | visual consumption
        v
PHYSICAL REORDER MARK REACHED
        |
        v
KANBAN CARD ACTIVATED/REMOVED
        |
        v
PURCHASE / REPLENISHMENT ENTRY IN PROLOWIN
        |
        v
ADMINISTRATION REVIEW + AUTHORIZATION
        |
        v
PURCHASE EXECUTION
        |
        v
RECEIVING VALIDATION REQUIREMENTS
        |
        v
MATERIAL ARRIVES
        |
        +--> COMPLIES --> ACCEPT --> REPLENISH CONTAINER
        |
        +--> DOES NOT COMPLY --> REJECT / RETURN
```

## Digitalization principle
The MOP must first mirror and trace this flow rather than replace it.

Initial digital objectives:
- identify each material/container/location/card;
- register reorder trigger;
- show current Kanban/replenishment state;
- calculate future consumption from Plan + Product + ABM;
- warn when projected demand may reach the trigger before replenishment;
- link the signal to Prolowin purchase-order/reference data;
- register receiving inspection outcome;
- measure supplier and replenishment performance.

## Important distinction
Physical state and projected state are different:
- **Physical Kanban state:** confirmed by operator/container/card.
- **Projected availability/risk:** calculated by MOP from production demand and known replenishment.

Both must be visible and must never be silently conflated.
