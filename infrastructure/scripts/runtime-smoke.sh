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
FIXTURE_FILE="$(mktemp)"
RBAC_USERS_FILE="$(mktemp)"
MATERIALS_FIXTURE_FILE="$(mktemp)"
RBAC_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"

cleanup() {
  rm -f "$COOKIE_JAR" "$HEADER_FILE" "$FIXTURE_FILE" "$RBAC_USERS_FILE" "$MATERIALS_FIXTURE_FILE"
  docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$ROOT"
# Fail quickly on malformed Chrome test scripts before provisioning Docker.
for browser_script in "$ROOT"/infrastructure/scripts/mes-*.mjs; do
  node --check "$browser_script"
done
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

docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api \
  python -c "from zoneinfo import ZoneInfo; assert ZoneInfo('America/Argentina/Cordoba').key == 'America/Argentina/Cordoba'"

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

# Seed canonical G2/G3/G4 data, publish APS, and release one real MES dispatch.
# Stream fixture source into the isolated API container without rebuilding the image.
SEED_LOG="$(docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api python - < "$ROOT/infrastructure/scripts/mes-browser-fixture.py")"
printf '%s\n' "$SEED_LOG" | sed -n 's/^MES_BROWSER_FIXTURE=//p' > "$FIXTURE_FILE"
if [[ ! -s "$FIXTURE_FILE" ]]; then
  echo "MES browser fixture did not return a dispatch manifest" >&2
  exit 1
fi

# G5.8 RBAC identities are test-only and scoped to the disposable CI database.
RBAC_LOG="$(docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T -e MOP_RBAC_TEST_PASSWORD="$RBAC_PASSWORD" api python - < "$ROOT/infrastructure/scripts/mes-rbac-fixture.py")"
printf '%s\n' "$RBAC_LOG" | sed -n 's/^MES_RBAC_USERS=//p' > "$RBAC_USERS_FILE"
if [[ ! -s "$RBAC_USERS_FILE" ]]; then
  echo "RBAC fixture did not return test users" >&2
  exit 1
fi

MOP_BROWSER_ORIGIN="http://127.0.0.1:$WEB_PORT" \
MOP_ADMIN_USERNAME="$ADMIN_USERNAME" \
MOP_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
MOP_RBAC_TEST_PASSWORD="$RBAC_PASSWORD" \
MOP_MES_RBAC_USERS_JSON="$RBAC_USERS_FILE" \
MOP_MES_FIXTURE_JSON="$FIXTURE_FILE" \
node "$ROOT/infrastructure/scripts/mes-rbac-browser.mjs"

# G6.8 synthetic material data for authenticated real-browser acceptance.
# Only copy test helpers into the disposable compose API container; do not alter
# the production image, existing mop-dev project, or any persistent FAIC data.
API_CONTAINER="$(docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps -q api)"
[[ -n "$API_CONTAINER" ]] || { echo "G6.8 disposable API container missing" >&2; exit 1; }
docker exec "$API_CONTAINER" mkdir -p /tmp/g68_fixture
docker cp "$ROOT/tests/g6/test_material_requirements_integration.py" "$API_CONTAINER:/tmp/g68_fixture/test_material_requirements_integration.py"
docker cp "$ROOT/tests/g6/test_reservations_integration.py" "$API_CONTAINER:/tmp/g68_fixture/test_reservations_integration.py"
MATERIALS_SEED_LOG="$(docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api python - < "$ROOT/infrastructure/scripts/g68-materials-fixture.py")"
printf '%s\n' "$MATERIALS_SEED_LOG" | sed -n 's/^G68_MATERIALS_FIXTURE=//p' > "$MATERIALS_FIXTURE_FILE"
[[ -s "$MATERIALS_FIXTURE_FILE" ]] || { echo "G6.8 materials fixture missing" >&2; exit 1; }
echo "G6.8 mixed-taquilla/materials synthetic fixture seeded in isolated PostgreSQL"

# Exercise the actual React application through headless Chrome while FastAPI and
# PostgreSQL containers are alive; this complements the HTTP/runtime checks.
MOP_BROWSER_ORIGIN="http://127.0.0.1:$WEB_PORT" \
MOP_ADMIN_USERNAME="$ADMIN_USERNAME" \
MOP_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
MOP_RBAC_TEST_PASSWORD="$RBAC_PASSWORD" \
MOP_MES_RBAC_USERS_JSON="$RBAC_USERS_FILE" \
MOP_MES_FIXTURE_JSON="$FIXTURE_FILE" \
MOP_G68_MATERIALS_FIXTURE_JSON="$MATERIALS_FIXTURE_FILE" \
node "$ROOT/infrastructure/scripts/mes-browser-smoke.mjs"

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
