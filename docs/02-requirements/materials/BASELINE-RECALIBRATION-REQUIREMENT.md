# Materials and Supplier Baseline Recalibration Requirement

Status: G0 requirement  
Date: 2026-10-27

## Problem statement
FAIC currently has no verifiable analytical baseline linking physical Kanban parameters to:
- current demand;
- current product mix;
- validated consumption;
- measured supplier lead time;
- supplier delivery variability;
- objective supplier performance.

Therefore the project must treat current values as migration inputs only.

## Required initial behavior
The platform must support a **shadow measurement period** in which it does not alter the current card parameters but captures the data needed to recalculate them.

## Minimum measured event chain

```text
KANBAN TRIGGER
   ↓
REQUEST CREATED
   ↓
ADMIN REVIEW
   ↓
PURCHASE ORDER / SUPPLY ORDER
   ↓
PROMISED DATE (if provided)
   ↓
PHYSICAL ARRIVAL
   ↓
RECEIVING INSPECTION
   ↓
ACCEPT / REJECT
   ↓
CONTAINER REPLENISHED
   ↓
CARD RETURNED
```

## Derived measurements
From these events MOP should later calculate:
- request-to-authorization time;
- authorization-to-order time;
- order-to-arrival lead time;
- total trigger-to-replenishment time;
- supplier promise adherence;
- lead-time median/average;
- lead-time variability;
- receiving conformity rate;
- rejection/return rate;
- replenishment-cycle frequency;
- shortage occurrences.

## Migration rule
Every current card parameter must carry:
- source = LEGACY_PHYSICAL_CARD;
- verification_status = UNVERIFIED;
- captured_at;
- effective_from, if known;
- superseded_by_policy_id, once recalibrated.

## Objective
Build a defensible, current and auditable replenishment system without interrupting current production while the new evidence base is formed.
