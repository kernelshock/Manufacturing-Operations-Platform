# G1.7 Runtime — DEV / TEST

This directory contains the reproducible single-host runtime baseline for MOP.

## Topology

```text
Browser
  |
  | HTTP on loopback in DEV/TEST
  v
Frontend / reverse proxy (nginx)
  |
  +--> static React application
  |
  +--> /api, /health, /docs
          |
          v
      FastAPI API
          |
          v
      PostgreSQL 18
```

The database and API ports are not published to the host by the Compose baseline. Only the frontend/reverse-proxy port is bound, and it is bound to `127.0.0.1` for DEV/TEST.

Production remains subject to ADR-0015: HTTPS on the plant network, controlled administrative access and production-specific certificate/reverse-proxy configuration.

## Prerequisites

- Docker Engine with Docker Compose v2;
- Linux/WSL2 shell for the helper scripts.

## First start

From repository root:

```bash
cp infrastructure/config/runtime.dev.env.example .env.runtime
```

Set a strong value for `MOP_POSTGRES_PASSWORD` in `.env.runtime`. The file is ignored by Git.

Generate a suitable secret, for example:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Start the stack:

```bash
./infrastructure/scripts/runtime-dev-up.sh
```

Open:
- application: `http://127.0.0.1:8080`;
- Swagger via the reverse proxy: `http://127.0.0.1:8080/docs`.

## Initial administrator

After the migrations complete:

```bash
./infrastructure/scripts/runtime-bootstrap-admin.sh
```

The command prompts for the administrator password without echoing it. The password is not written to the repository or Compose file.

For non-interactive automation only, `MOP_BOOTSTRAP_ADMIN_PASSWORD` may be supplied in the process environment.

## Stop

```bash
./infrastructure/scripts/runtime-dev-down.sh
```

The PostgreSQL named volume is preserved. To intentionally destroy DEV data:

```bash
docker compose --project-name mop-dev --env-file .env.runtime \
  -f infrastructure/compose/compose.dev.yml down -v
```

## Migrations

`migrate` is a one-shot service. The API does not start until:
1. PostgreSQL reports healthy;
2. `python -m alembic upgrade head` exits successfully.

This prevents the application from accepting traffic against an outdated schema.

## Secrets

Runtime credentials are injected from an ignored environment file or process environment. They are not baked into container images.

MOP builds the PostgreSQL SQLAlchemy URL from discrete database components. This permits special characters in the database password without unsafe string interpolation.

## Reverse proxy and source address

nginx generates/preserves request correlation headers and forwards client-address headers. The API is not published by Compose, so Uvicorn trusts proxy headers only inside this container topology.

## Background worker boundary

ADR-0015 includes a background worker in the target topology. G1.7 does not create a fake worker process because no persistent job/outbox worker has yet been implemented. When the worker contract is introduced, it must reuse the backend image, configuration boundary and PostgreSQL runtime rather than adding a parallel stack.

## Test runtime

`runtime.test.env.example` defines a separate test naming/port profile. CI executes `runtime-smoke.sh`, which:
- validates Compose configuration;
- builds the backend and frontend images;
- starts PostgreSQL;
- applies migrations from a clean database;
- waits for readiness through the reverse proxy;
- verifies the React application;
- bootstraps an administrator;
- authenticates through the public runtime boundary;
- verifies `/auth/me` and audit access;
- destroys the test volume afterward.


## PostgreSQL 18 volume layout

The official PostgreSQL 18 image changed its persistent-volume root. G1.7 therefore mounts the named volume at:

`/var/lib/postgresql`

Do not revert this runtime to the pre-18 mount target `/var/lib/postgresql/data`.
