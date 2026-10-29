#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT/.env.runtime}"
COMPOSE_FILE="$ROOT/infrastructure/compose/compose.dev.yml"
PROJECT="${MOP_COMPOSE_PROJECT:-mop-dev}"

cd "$ROOT"
docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down --remove-orphans
