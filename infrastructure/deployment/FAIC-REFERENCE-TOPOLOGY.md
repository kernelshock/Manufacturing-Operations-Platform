# FAIC Reference Deployment Topology

Status: G0 baseline
Date: 2026-10-28

## Target deployment

```text
FAIC LAN
│
├── Operator / Supervisor browsers
│
└── HTTPS
     │
     ▼
┌───────────────────────────────┐
│ Linux Server / VM             │
│                               │
│  Reverse Proxy                │
│      │                        │
│      ├── Web Frontend         │
│      └── MOP API              │
│             │                 │
│             ├── Worker        │
│             ├── PostgreSQL    │
│             └── Import Area   │
│                               │
└───────────────────────────────┘
          │
          ├── Backup target
          │
          └── Controlled external-system files
                ├── Prolowin exports
                └── future adapters
```

## Deployment profiles

### DEV
Developer workstation/WSL or isolated Linux environment.

### TEST/SIMULATION
Isolated data and configuration; synthetic or controlled imported datasets.

### SHADOW/PARALLEL
Production-like server using real operational feeds while legacy process remains authoritative.

### PRODUCTION
MOP becomes authoritative only for explicitly released domains.

## Container services
Initial deployment may package:
- reverse-proxy;
- frontend;
- api;
- worker;
- postgres.

No Kubernetes is required.

## Minimum host characteristics
Exact sizing is deferred until G1/G2 measurements. The topology requires:
- supported 64-bit Linux host/VM;
- persistent storage;
- reliable LAN access;
- secure backup destination;
- controlled administrator access;
- time synchronization;
- adequate memory/CPU for PostgreSQL and application workload.

APS compute needs are measured before G4 and may justify additional worker capacity later.

## Client requirement
Normal users require only a supported modern browser and network access to the MOP HTTPS endpoint.

No direct PostgreSQL or host access is required for operators.
