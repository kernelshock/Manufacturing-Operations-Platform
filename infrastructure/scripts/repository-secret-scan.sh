#!/usr/bin/env bash
set -euo pipefail

fail=0

if git grep -nE -- '-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----' -- .; then
  echo "Private key material detected in tracked files." >&2
  fail=1
fi

if git grep -nE -- 'MOP_(POSTGRES_PASSWORD|BOOTSTRAP_ADMIN_PASSWORD)=[^[:space:]$][^[:space:]]*' -- .; then
  echo "Static MOP secret assignment detected in tracked files." >&2
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "Tracked-file secret baseline passed."
