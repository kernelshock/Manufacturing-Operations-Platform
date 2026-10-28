# ADR-0013 — Master Data Owns Manufacturing Definition

Status: Accepted  
Date: 2026-10-28

## Context
Prolowin contains product/article structure and routing evidence. Materials requires BOM demand; APS requires routing/capacity. Allowing each module to maintain its own manufacturing definition would create revision divergence.

## Decision
Master Data is the sole canonical owner of:
- Article and ArticleRevision;
- UoM and source mappings;
- BOMRevision and ComponentRelation;
- RoutingRevision and RoutingOperation;
- manufacturing-definition source mappings.

Materials consumes the effective BOM and stores operational/material state only.

APS consumes the effective Routing/BOP and stores schedules/constraint decisions only.

MES references the published revision used by execution.

## Consequences
- one revision model across modules;
- historical plans/executions retain exact manufacturing-definition revision IDs;
- importer ownership belongs to Integration Hub, while canonical application targets Master Data;
- no direct Materials or APS table becomes an alternative BOM/routing source.
