# e-Kanban Functional Model — FAIC Baseline

Status: Draft validated from current-state observations  
Date: 2026-10-27

## 1. Core operating rule

A Kanban card represents a **specific material within one physical replenishment loop / point-of-use supply circuit**.

That replenishment loop may supply:
- one product;
- several products in the same area;
- one productive area;
- or, where the physical supply arrangement is shared, more than one productive area.

A material may have one or more physical containers associated with the same replenishment loop, but only one Kanban card for that loop.

Therefore the operational identity is better represented as:

```text
Material + Replenishment Loop + Kanban Card
```

The products and productive areas are **consumers linked to that replenishment loop**, not part of the card identity itself.

## 2. Cardinality

```text
MATERIAL
   |
   | 1..n workplaces may consume it
   v
PRODUCTIVE WORKPLACE
   |
   | 1 Kanban card per material/workplace
   v
KANBAN CARD
   |
   | 1..n
   v
PHYSICAL CONTAINERS
```

This means:
- one material can be shared by several products and/or workplaces;
- each consuming workplace controls its own replenishment signal;
- several physical containers may support the same local replenishment loop;
- only one card represents that local loop.

## 3. Supplier/origin type

Card color communicates origin:

- RED = external supplier;
- ORANGE = internal supplier.

The digital model must store supplier/origin type explicitly. Color is a visual representation, not the only source of meaning.

Suggested field:

```text
supply_source_type:
  EXTERNAL
  INTERNAL
```

## 4. Minimum Kanban card data

Based on current FAIC cards, the digital object should support at least:

- card_id
- material_code
- material_description
- requesting_sector_code
- requesting_sector_name
- productive_center
- storage_location
- drawing_or_specification_reference
- unit_of_measure
- reorder_point
- replenishment_quantity
- supply_source_type
- visual_color
- workplace_id
- active
- revision/version
- notes / optional material-specific fields

Additional material-specific information may be supported through controlled extensible attributes.

## 5. Container model

A Kanban card may reference one or more physical containers.

Container data should support:

- container_id
- kanban_card_id
- workplace_id
- storage_location
- nominal_capacity, when known
- physical_trigger_mark
- active
- notes

Exact capacity is not mandatory for the first release if FAIC currently operates by physical/volumetric trigger rather than precise count.

## 6. Replenishment lifecycle

Current physical workflow:

```text
AVAILABLE AT POINT OF USE
        |
        | consumption
        v
PHYSICAL REORDER LEVEL REACHED
        |
        v
CARD REMOVED / ACTIVATED
        |
        v
REPLENISHMENT REQUEST ENTERED IN PROLOWIN
        |
        v
ADMINISTRATION REVIEW
        |
        v
AUTHORIZED
        |
        v
PURCHASE / INTERNAL SUPPLY
        |
        v
IN TRANSIT / PENDING DELIVERY
        |
        v
RECEIVING + VALIDATION
        |
        +--> CONFORMING
        |       |
        |       v
        |   MATERIAL REPLENISHED
        |       |
        |       v
        |   CARD RETURNS TO CONTAINER
        |       |
        |       v
        |   AVAILABLE
        |
        +--> NONCONFORMING
                |
                v
          REJECT / RETURN
                |
                v
        REPLENISHMENT REMAINS OPEN
```

## 7. Digital state model

Suggested states:

- AVAILABLE
- TRIGGER_REACHED
- REQUESTED
- UNDER_REVIEW
- APPROVED
- ORDERED
- IN_TRANSIT
- RECEIVING_INSPECTION
- REJECTED
- RETURN_REQUIRED
- REPLENISHED
- AVAILABLE

The same card is reused cycle after cycle.

## 8. Critical rule: card lifecycle

The card is **not consumed or archived** after replenishment.

After compliant material is received and the local containers are replenished:

```text
KanbanCard.status = AVAILABLE
```

and the physical card returns to the point-of-use container.

Every cycle must therefore create a separate historical transaction:

```text
KANBAN_CARD
    |
    +--> REPLENISHMENT_CYCLE #1
    +--> REPLENISHMENT_CYCLE #2
    +--> REPLENISHMENT_CYCLE #3
    ...
```

This preserves history without replacing the card.

## 9. Replenishment cycle object

Each activation should create a new `ReplenishmentCycle` with:

- cycle_id
- kanban_card_id
- trigger_timestamp
- triggered_by
- reorder_point_at_trigger
- replenishment_quantity_requested
- Prolowin_reference, when available
- approval_status
- approved_by
- order_reference
- supplier/source
- expected_delivery_date
- received_date
- inspection_result
- rejected_quantity, when applicable
- rejection_reason
- closed_at
- cycle_status

## 10. Physical vs projected state

Two layers remain separate.

### Physical truth
Confirmed by:
- card;
- containers;
- operator;
- receiving/replenishment event.

### Projected risk
Calculated by MOP from:
- Plan;
- Taquilla;
- Product;
- ABM/BOM;
- planned demand;
- execution;
- replenishment quantity;
- lead time;
- known purchase/order status.

MOP may predict that a trigger will occur, but it must not silently mark the physical card as triggered without operator confirmation in the initial maturity level.

## 11. Shared materials and aggregated demand

A material shared across products does not require one card per product when those products are supplied by the same physical replenishment loop.

Likewise, if one physical replenishment loop supplies more than one productive area, the same card can represent the aggregated requirement of those areas.

The card identity follows the **physical replenishment circuit**, not an individual product.

Products and areas consume through explicit relationships to the material/replenishment loop. The reorder point and replenishment policy must therefore consider the combined expected consumption of all linked consumers.

Conceptually:

```text
Product A ----\
Product B -----+--> Material X --> Replenishment Loop KX --> Kanban Card KX
Area 1 -------/
Area 2 ------/
```

The same material may still have another independent replenishment loop elsewhere in the plant, with its own card, containers, reorder point and replenishment quantity.

## 12. Design principle

The first digital implementation must:

1. preserve the physical card;
2. mirror its status digitally;
3. create a traceable replenishment cycle;
4. connect the cycle to Prolowin;
5. capture receiving validation;
6. calculate future risk;
7. avoid requiring exact perpetual inventory;
8. allow later migration to barcode/QR/RFID or exact stock without changing the domain model.
