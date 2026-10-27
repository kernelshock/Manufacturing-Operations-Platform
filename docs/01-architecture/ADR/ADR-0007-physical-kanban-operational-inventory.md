# ADR-0007 — Physical Point-of-Use Kanban as Initial Operational Inventory Truth

Status: Accepted  
Date: 2026-10-27

## Context
FAIC does not currently maintain a reliable perpetual digital stock balance for production materials.

Consumables and production materials are stored at their point of use in each productive area. Containers have physical marks that indicate the reorder threshold. When the material reaches that level, the operator takes the physical Kanban card and initiates the purchase/replenishment request in Prolowin.

The configuration varies by:
- productive area;
- material;
- product family;
- container;
- shared use across multiple products.

Materials are physically close to the productive area, so the review/inspection cadence is effectively continuous during normal operation.

## Decision
The first Materials implementation will **not require exact perpetual inventory quantities** as its operational truth.

The authoritative initial operational state is:
- point-of-use location;
- material/container identity;
- physical trigger/reorder level;
- Kanban card state;
- replenishment state.

The Manufacturing Operations Platform (MOP) will digitize this system as an e-Kanban layer while preserving the existing physical control during migration.

## Initial Kanban state model
A material-location/container may move through states such as:

AVAILABLE → APPROACHING_TRIGGER → REORDER_TRIGGERED → REQUESTED → APPROVED → ORDERED → IN_TRANSIT → RECEIVING_INSPECTION → REPLENISHED

A nonconforming receipt may move to:
REJECTED / RETURN_REQUIRED

## Planning layer
MOP may maintain a **projected/virtual availability** derived from:
- ABM/BOM requirements;
- released production plans;
- actual production execution;
- known replenishments;
- supplier lead time;
- Kanban trigger configuration.

Projected availability is decision-support information and must not be represented as a physically counted quantity unless validated by a physical transaction/counting process.

## Replenishment workflow
Current-state sequence to preserve:

1. operator visually detects physical trigger level;
2. operator removes/activates Kanban card;
3. purchase/replenishment is entered in Prolowin;
4. Administration reviews and authorizes;
5. purchase is executed;
6. receiving requirements/validation document is issued;
7. material is received and inspected;
8. if compliant, material is accepted and replenishes the point-of-use container;
9. if nonconforming, product should be rejected/returned according to the applicable control.

## Consequences
- Initial MOP deployment can coexist with physical cards.
- Exact stock counting is not imposed abruptly.
- APS can forecast material risk from future demand before the physical trigger is reached.
- Human confirmation remains authoritative for the physical Kanban trigger during early maturity levels.
- Later maturity may introduce barcode/QR/RFID, container scans, exact receipts/issues or perpetual inventory without changing the canonical model.
- Incoming inspection requirements must be represented even if a full Quality module is deferred.


## Clarified cardinality
Confirmed during G0:
- one Kanban card represents one material at one productive workplace;
- the same local material loop may have multiple physical containers;
- there is only one card for that material/workplace combination;
- if the same material is consumed at another workplace, that workplace has its own card and containers;
- after a compliant replenishment, the same card returns to the container and is reused for the next replenishment cycle.


## Refined replenishment-loop rule
Further G0 clarification:
- the Kanban card is not tied to a single product;
- one physical replenishment loop may supply multiple products;
- where the same physical supply circuit serves multiple productive areas, their demand is aggregated into the same Kanban policy;
- the reorder point must reflect total expected consumption from all consumers linked to that replenishment loop;
- the same material may have separate replenishment loops elsewhere, each with independent card, containers, PP and replenishment quantity.
