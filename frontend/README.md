# MOP Frontend — G1.6 Shell

React + TypeScript + Vite browser shell for the Manufacturing Operations Platform.

## Local development

Requirements:
- Node.js 24 or 26;
- backend running on `127.0.0.1:8000`.

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

Vite proxies `/api` and `/health` to the local FastAPI process, preserving same-origin cookie behavior from the browser perspective.

## Validation

```bash
npm run typecheck
npm test
npm run build
```

## Security boundary

The browser never receives password hashes or raw authorization state from the database. It consumes the versioned REST API, sends the opaque session cookie with `credentials: include`, and uses effective permission codes returned by `/api/v1/auth/me` only to shape navigation. Backend authorization remains authoritative.

A hidden/disabled UI function is not a security control. Every privileged API remains protected server-side.

## G3.7 operational surface

In addition to the original G1 shell, the frontend now exposes a permission-driven Demand module for `demand.read` / `demand.edit`:

- Production Plan selector;
- Plan → ordered Taquilla operational projection;
- product Article code/description, requested quantity and explicit deck position;
- exact RoutingRevision binding state and missing-routing blockers;
- historical completion/cancellation visibility;
- REVIEW_REQUIRED assimilation queue;
- normalized Taquilla JSON import for users with `demand.edit`.

The browser does not parse source PDFs or infer floor/product semantics. It submits the explicit G3.6 normalized assimilation contract and relies on the backend for validation and authorization.

APS sequencing, finite capacity, Gantt and MES actuals remain outside this frontend surface.

## Original G1.6 surface

- secure login shell;
- current-user/session bootstrap;
- backend metadata/readiness display;
- permission-driven module navigation;
- organization/plant context selector when the current user has global read capabilities;
- audit read surface for `audit.read`;
- administration shell for administrative capabilities;
- placeholders for G2+ APS, MES, Kanban, Maintenance and Purchasing modules.

Full business-module workflows are intentionally outside G1.6.
