# ADR-0018 — Single-Tenant Runtime with Multi-Plant Domain Model

Status: Accepted  
Date: 2026-10-28

## Decision
The first production release is **single-tenant per deployment** but the canonical domain supports multiple plants and organizational units.

Initial hierarchy:

```text
Organization
  -> Plant
      -> Area
          -> WorkCenter
              -> Resource
```

FAIC is one deployment/tenant in the initial product.

## Data model
Operational records that are plant-specific carry explicit plant/organization context through their owning aggregates.

Global deployment-level masters may be shared only where domain rules explicitly permit it.

## Multi-industry strategy
The platform becomes reusable through:
- versioned configuration;
- tenant/deployment-specific configuration;
- plant/process/resource masters;
- adapters;
- permissions;
not through FAIC-specific code forks.

## Deferred
A true shared-database SaaS multi-tenant runtime with tenant row-level isolation is deferred.

If commercial strategy later requires hosted multi-tenancy, it will be introduced by a dedicated security/data-isolation ADR and migration plan.

## Rationale
This gives FAIC immediate simplicity while preserving multi-plant semantics and avoiding premature SaaS complexity.
