#!/usr/bin/env bash
set -euo pipefail

fail=0

unpinned_actions="$(
  grep -RInE '^[[:space:]]*uses:[[:space:]]+[^[:space:]#]+@v[0-9]+' .github/workflows || true
)"
if [[ -n "$unpinned_actions" ]]; then
  printf '%s\n' "$unpinned_actions"
  echo "GitHub Actions must be pinned to immutable commit SHAs." >&2
  fail=1
fi

unpinned_from="$(
  grep -RInE '^FROM[[:space:]]+[^[:space:]]+$' infrastructure/docker/*.Dockerfile |
    grep -v '@sha256:' || true
)"
if [[ -n "$unpinned_from" ]]; then
  printf '%s\n' "$unpinned_from"
  echo "Docker base images must be pinned by sha256 digest." >&2
  fail=1
fi

if ! grep -qE 'image:[[:space:]]+postgres:18@sha256:[0-9a-f]{64}' infrastructure/compose/compose.dev.yml; then
  echo "PostgreSQL Compose image is not pinned by sha256 digest." >&2
  fail=1
fi

for lock in requirements-prod.lock.txt requirements-dev.lock.txt frontend/package-lock.json; do
  if [[ ! -s "$lock" ]]; then
    echo "Missing or empty dependency lock: $lock" >&2
    fail=1
  fi
done

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "Supply-chain pin baseline passed."
