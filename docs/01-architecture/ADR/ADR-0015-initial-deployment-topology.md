# ADR-0015 — Initial Deployment Topology

Status: Accepted  
Date: 2026-10-28

## Decision
The reference FAIC deployment is **on-premise / plant-network, browser-based, containerized on a dedicated Linux host or Linux VM**.

Preferred topology:

```text
Plant browsers/tablets
        |
     HTTPS
        |
Reverse Proxy
        |
        +--> Web Frontend
        |
        +--> MOP API / Modular Monolith
                  |
                  +--> Background Worker
                  |
                  +--> PostgreSQL
                  |
                  +--> Controlled import/export directories
```

## Packaging
- Docker containers
- Docker Compose for the initial single-host production topology
- persistent volumes for PostgreSQL and controlled application data
- environment-specific configuration outside images

## Network
- intranet-first;
- HTTPS even on the internal network;
- database not directly exposed to operator clients;
- only reverse-proxy/application ports exposed;
- administrative access restricted.

## Availability profile
G1–G12 do not require Kubernetes or a clustered database.

The application must be restartable and recoverable on a replacement Linux VM using:
- release artifacts/images;
- versioned configuration;
- database backup;
- controlled document/import storage backup.

## Infrastructure uncertainty
FAIC's exact current server inventory is not yet documented. This ADR defines the **reference topology**, not a claim about existing hardware.

If FAIC infrastructure cannot host Linux containers directly, the same topology may run in an approved Linux VM on existing virtualization.

## Consequences
- implementation can start without server-vendor dependency;
- deployment is portable across physical server, VM and later cloud/private-cloud targets;
- Kubernetes is explicitly deferred until scale/HA requirements justify it.
