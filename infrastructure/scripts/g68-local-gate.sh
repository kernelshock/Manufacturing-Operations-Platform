#!/usr/bin/env bash
# G6.8 local acceptance. Uses disposable PostgreSQL and a uniquely named runtime compose stack.
# No operation against an existing production DB. Logs remain on the local machine.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
BRANCH="feat/G6-materials"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || { echo "ERROR: checkout $BRANCH" >&2; exit 2; }
[[ -z "$(git status --porcelain --untracked-files=normal)" ]] || { echo "ERROR: working tree is not clean" >&2; git status --short; exit 2; }
git fetch origin "$BRANCH" --quiet
[[ "$(git rev-parse HEAD)" == "$(git rev-parse "origin/$BRANCH")" ]] || { echo "ERROR: local HEAD differs from origin/$BRANCH" >&2; exit 2; }
command -v docker >/dev/null
docker info >/dev/null
command -v node >/dev/null
command -v npm >/dev/null
command -v google-chrome >/dev/null || { echo "ERROR: google-chrome is required for the runtime browser gate" >&2; exit 2; }
PYTHON_BIN="${MOP_G68_PYTHON:-python3.14}"
command -v "$PYTHON_BIN" >/dev/null || { echo "ERROR: Python 3.14 required; set MOP_G68_PYTHON" >&2; exit 2; }
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] == (3,14)'
"$PYTHON_BIN" -c 'import alembic,pytest,psycopg,sqlalchemy,fastapi' || {
  echo "ERROR: missing G6 Python dependencies. Install locked dev dependencies in a dedicated venv first." >&2
  exit 2
}
SESSION="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short=9 HEAD)-$$"
OUT="$ROOT/runtime-data/g68/$SESSION"
mkdir -p "$OUT"
chmod 700 "$OUT"
echo "=== G6.8 LOCAL GATE ==="
echo "HEAD $(git rev-parse HEAD)"
echo "Evidence: $OUT"
printf '%s\n' "$(git rev-parse HEAD)" > "$OUT/commit.txt"
CONTAINER="mop-g68-pg-$$"
PROJECT="mop-g68-runtime-$$"
DB_PASSWORD="$("$PYTHON_BIN" -c 'import secrets;print(secrets.token_urlsafe(30))')"
ADMIN_PASSWORD="$("$PYTHON_BIN" -c 'import secrets;print(secrets.token_urlsafe(30))')"
ENV_FILE="$OUT/.env.runtime-ci"
export MOP_ENVIRONMENT=test
export MOP_DATABASE_URL=""
cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  unset MOP_DATABASE_URL
}
trap cleanup EXIT
trap 'rc=$?; echo "ERROR G6.8 line=$LINENO command=$BASH_COMMAND exit=$rc" | tee -a "$OUT/summary.txt" >&2' ERR
fail() {
  local status=$?
  printf 'FAIL %s exit=%s\n' "$1" "$status" | tee -a "$OUT/summary.txt" >&2
  exit "$status"
}
run_stage() {
  local label="$1"; shift
  echo "RUN $label" | tee -a "$OUT/summary.txt"
  if "$@" > "$OUT/$label.log" 2>&1; then
    echo "PASS $label" | tee -a "$OUT/summary.txt"
  else
    local rc=$?
    echo "FAIL $label exit=$rc (see $OUT/$label.log)" | tee -a "$OUT/summary.txt" >&2
    tail -n 35 "$OUT/$label.log" >&2 || true
    exit "$rc"
  fi
}

# Disposable PostgreSQL: randomly allocated loopback port, no shared database/volume.
docker run -d --rm --name "$CONTAINER" -e POSTGRES_DB=mop_g68 -e POSTGRES_USER=mop_g68 \
  -e "POSTGRES_PASSWORD=$DB_PASSWORD" -p 127.0.0.1::5432 \
  'postgres:18@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4' > "$OUT/postgres-container.txt" 2> "$OUT/postgres-start.err" || {
  echo "FAIL postgres setup; see $OUT/postgres-start.err" >&2; exit 1;
}
# docker run --detach returns before bridge port mapping and initdb are ready.
# Retry both observables. On failure preserve diagnostics before EXIT cleanup.
echo "RUN postgres_ready" | tee -a "$OUT/summary.txt"
PORT=""
READY=0
for _ in $(seq 1 60); do
  mapping="$(docker port "$CONTAINER" 5432/tcp 2>> "$OUT/postgres-port.err" || true)"
  PORT="$(printf '%s\n' "$mapping" | awk -F: 'NR==1 && NF>=2 {print $NF}')"
  if [[ "$PORT" =~ ^[0-9]+$ ]] &&
      docker exec "$CONTAINER" pg_isready -U mop_g68 -d mop_g68 >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done
if [[ "$READY" -ne 1 ]]; then
  echo "FAIL postgres_ready: missing port or pg_isready timed out" | tee -a "$OUT/summary.txt" >&2
  docker inspect "$CONTAINER" > "$OUT/postgres-inspect.json" 2>&1 || true
  docker logs "$CONTAINER" > "$OUT/postgres.log" 2>&1 || true
  docker port "$CONTAINER" 5432/tcp > "$OUT/postgres-ports.txt" 2>&1 || true
  tail -n 35 "$OUT/postgres.log" >&2 || true
  exit 1
fi
echo "PASS postgres_ready (loopback port allocated)" | tee -a "$OUT/summary.txt"
export MOP_DATABASE_URL="postgresql+psycopg://mop_g68:$DB_PASSWORD@127.0.0.1:$PORT/mop_g68"
run_stage migration_upgrade "$PYTHON_BIN" -m alembic upgrade head
run_stage migration_check "$PYTHON_BIN" -m alembic check
run_stage migration_downgrade "$PYTHON_BIN" -m alembic downgrade base
run_stage migration_replay "$PYTHON_BIN" -m alembic upgrade head
run_stage migration_replay_check "$PYTHON_BIN" -m alembic check
run_stage backend_g0_g6 "$PYTHON_BIN" -m pytest tests/g0 tests/g1 tests/g2 tests/g3 tests/g4 tests/g5 tests/g6 -q -ra
run_stage supply_chain bash -c './infrastructure/scripts/repository-secret-scan.sh && ./infrastructure/scripts/supply-chain-pin-check.sh'
run_stage frontend_install bash -c 'cd frontend && npm ci --no-fund'
run_stage frontend_audit bash -c 'cd frontend && npm audit --audit-level=high'
run_stage frontend_typecheck bash -c 'cd frontend && npm run typecheck'
run_stage frontend_tests bash -c 'cd frontend && npm test'
run_stage frontend_build bash -c 'cd frontend && npm run build'

# Runtime smoke creates and destroys ONLY its own distinct Compose project.
# Its env file contains test credentials: restricted local evidence directory, never commit it.
cat > "$ENV_FILE" <<EOF
MOP_ENVIRONMENT=test
MOP_POSTGRES_DB=mop_smoke
MOP_POSTGRES_USER=mop_smoke
MOP_POSTGRES_PASSWORD=$DB_PASSWORD
MOP_WEB_HOST_PORT=18080
MOP_SESSION_TTL_MINUTES=30
MOP_SESSION_COOKIE_SECURE=false
MOP_LOGIN_MAX_FAILURES=5
MOP_LOGIN_LOCKOUT_MINUTES=15
MOP_ADMIN_USERNAME=smoke-admin
MOP_ADMIN_DISPLAY_NAME=MOP Smoke Administrator
EOF
chmod 600 "$ENV_FILE"
# Runtime script cleans its own Compose project and volume via EXIT trap.
# Do not run with a populated MOP_COMPOSE_PROJECT or an occupied local port.
if [[ -n "${MOP_COMPOSE_PROJECT:-}" ]]; then
  echo "ERROR: unset MOP_COMPOSE_PROJECT for isolated runtime" >&2; exit 2
fi
if (echo > /dev/tcp/127.0.0.1/18080) >/dev/null 2>&1; then
  echo "ERROR: port 18080 already listening; refusing runtime launch" >&2; exit 2
fi
# The runtime smoke invokes `python` on the WSL host. Propagate the selected
# Python 3.14 environment instead of relying on a system `python` symlink.
# Resolve the venv bin directory without dereferencing the Python symlink.
PYTHON_EXEC="$(command -v "$PYTHON_BIN")"
PYTHON_HOST_BIN="$(cd "$(dirname "$PYTHON_EXEC")" && pwd)"
run_stage chrome_runtime env PATH="$PYTHON_HOST_BIN:$PATH" \
  MOP_COMPOSE_PROJECT="$PROJECT" MOP_WEB_HOST_PORT=18080 \
  MOP_ADMIN_USERNAME=smoke-admin MOP_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  MOP_G68_SCREENSHOT_FILE="$OUT/materials-browser.png" \
  bash infrastructure/scripts/runtime-smoke.sh "$ENV_FILE"
echo "ALL CONFIGURED LOCAL G6.8 CHECKS PASSED" | tee -a "$OUT/summary.txt"
echo "Evidence saved: $OUT (check logs, skips and evidence scope before release)"
