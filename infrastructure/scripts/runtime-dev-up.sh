#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT/.env.runtime}"
COMPOSE_FILE="$ROOT/infrastructure/compose/compose.dev.yml"
PROJECT="${MOP_COMPOSE_PROJECT:-mop-dev}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Runtime env file not found: $ENV_FILE" >&2
  echo "Create it with:" >&2
  echo "  cp infrastructure/config/runtime.dev.env.example .env.runtime" >&2
  exit 2
fi

cd "$ROOT"
docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config -q
docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build postgres migrate api frontend
docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo
echo "MOP DEV runtime: http://127.0.0.1:${MOP_WEB_HOST_PORT:-8080}"
echo "Swagger through reverse proxy: http://127.0.0.1:${MOP_WEB_HOST_PORT:-8080}/docs"
