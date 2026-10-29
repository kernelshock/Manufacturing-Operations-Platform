#!/usr/bin/env bash
set -euo pipefail

fail=0

if git grep -nE -- '-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----' -- .   ':!infrastructure/scripts/repository-secret-scan.sh'; then
  echo "Private key material detected in tracked files." >&2
  fail=1
fi

matches="$(
  git grep -nE -- 'MOP_(POSTGRES_PASSWORD|BOOTSTRAP_ADMIN_PASSWORD)=' -- .     ':!infrastructure/scripts/repository-secret-scan.sh' || true
)"

if [[ -n "$matches" ]]; then
  unsafe="$(
    printf '%s\n' "$matches" |
      grep -vE 'MOP_(POSTGRES_PASSWORD|BOOTSTRAP_ADMIN_PASSWORD)=$' |
      grep -vE '\$\{|\$[A-Za-z_][A-Za-z0-9_]*|secrets\.token_urlsafe|getpass\.' || true
  )"
  if [[ -n "$unsafe" ]]; then
    printf '%s\n' "$unsafe"
    echo "Static MOP secret assignment detected in tracked files." >&2
    fail=1
  fi
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "Tracked-file secret baseline passed."
