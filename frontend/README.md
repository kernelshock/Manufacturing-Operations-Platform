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

## G1.6 surface

- secure login shell;
- current-user/session bootstrap;
- backend metadata/readiness display;
- permission-driven module navigation;
- organization/plant context selector when the current user has global read capabilities;
- audit read surface for `audit.read`;
- administration shell for administrative capabilities;
- placeholders for G2+ APS, MES, Kanban, Maintenance and Purchasing modules.

Full business-module workflows are intentionally outside G1.6.
