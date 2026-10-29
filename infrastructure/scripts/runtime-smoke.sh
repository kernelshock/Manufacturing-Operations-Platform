#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT/.env.runtime-ci}"
COMPOSE_FILE="$ROOT/infrastructure/compose/compose.dev.yml"
PROJECT="${MOP_COMPOSE_PROJECT:-mop-g1-smoke}"
WEB_PORT="${MOP_WEB_HOST_PORT:-18080}"
ADMIN_USERNAME="${MOP_ADMIN_USERNAME:-smoke-admin}"
ADMIN_PASSWORD="${MOP_BOOTSTRAP_ADMIN_PASSWORD:?Set MOP_BOOTSTRAP_ADMIN_PASSWORD for runtime smoke test}"
COOKIE_JAR="$(mktemp)"
HEADER_FILE="$(mktemp)"

cleanup() {
  rm -f "$COOKIE_JAR" "$HEADER_FILE"
  docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$ROOT"
docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config -q
docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build postgres migrate api frontend

READY=0
for _ in $(seq 1 60); do
  if curl --fail --silent --show-error "http://127.0.0.1:$WEB_PORT/health/ready" >/tmp/mop-ready.json 2>/dev/null; then
    READY=1
    break
  fi
  sleep 2
done

if [[ "$READY" -ne 1 ]]; then
  docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
  docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --no-color
  exit 1
fi

grep -q '"status":"ready"' /tmp/mop-ready.json
curl --fail --silent --show-error -D "$HEADER_FILE" "http://127.0.0.1:$WEB_PORT/" -o /tmp/mop-index.html
grep -q "MOP · Manufacturing Operations Platform" /tmp/mop-index.html
grep -qi '^X-Content-Type-Options: nosniff' "$HEADER_FILE"
grep -qi '^X-Frame-Options: DENY' "$HEADER_FILE"
grep -qi '^Content-Security-Policy:' "$HEADER_FILE"

MOP_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm \
  -e MOP_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  bootstrap-admin

curl --fail --silent --show-error \
  -c "$COOKIE_JAR" \
  -D "$HEADER_FILE" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" \
  "http://127.0.0.1:$WEB_PORT/api/v1/auth/login" >/tmp/mop-login.json

grep -qi '^Cache-Control: no-store' "$HEADER_FILE"

curl --fail --silent --show-error \
  -b "$COOKIE_JAR" \
  "http://127.0.0.1:$WEB_PORT/api/v1/auth/me" >/tmp/mop-me.json

grep -q "\"username\":\"$ADMIN_USERNAME\"" /tmp/mop-me.json
curl --fail --silent --show-error -b "$COOKIE_JAR" "http://127.0.0.1:$WEB_PORT/api/v1/audit/events?limit=5" >/tmp/mop-audit.json

RATE_LIMITED=0
for _ in $(seq 1 20); do
  code="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    -H "Content-Type: application/json" \
    -d '{"username":"nonexistent-rate-test","password":"invalid-password"}' \
    "http://127.0.0.1:$WEB_PORT/api/v1/auth/login")"
  if [[ "$code" == "429" ]]; then
    RATE_LIMITED=1
    break
  fi
done

if [[ "$RATE_LIMITED" -ne 1 ]]; then
  echo "Login rate limiter did not return HTTP 429." >&2
  exit 1
fi

echo "MOP runtime smoke test passed."
