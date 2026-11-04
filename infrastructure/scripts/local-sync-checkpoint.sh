#!/usr/bin/env bash
# MOP local checkpoint: safe status/sync; no force, reset, stash or auto-commit.
set -euo pipefail

MODE="${1:-status}"
BRANCH="${2:-feat/G6-materials}"
if [[ "$MODE" != "status" && "$MODE" != "sync" ]]; then
  echo "Usage: $0 [status|sync] [branch]" >&2; exit 2
fi
if [[ "$BRANCH" == -* || "$BRANCH" == *".."* ]] || ! git check-ref-format --branch "$BRANCH" >/dev/null 2>&1; then
  echo "Invalid branch name: $BRANCH" >&2; exit 2
fi
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Run inside the MOP Git checkout." >&2; exit 2;
}
cd "$ROOT"
remote_url="$(git remote get-url origin)"
if [[ "$remote_url" != *"kernelshock/Manufacturing-Operations-Platform"* ]]; then
  echo "Unexpected origin: $remote_url" >&2
  echo "Verify repository identity before synchronization." >&2
  exit 2
fi

echo "=== MOP LOCAL CHECKPOINT ==="
echo "Repository: $ROOT"
echo "Mode: $MODE"
echo "Current branch: $(git branch --show-current)"
echo "Current HEAD: $(git rev-parse --short=12 HEAD)"
echo "Remote: $remote_url"
echo "=== Working tree ==="
git status --short
dirty="$(git status --porcelain=v1 --untracked-files=normal)"
if [[ "$MODE" == "sync" && -n "$dirty" ]]; then
  echo "BLOCKED: local modifications or untracked files found; no automatic stash/reset." >&2
  exit 3
fi
echo "=== Fetching remote refs without changing local files ==="
git fetch --prune origin
if ! git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  echo "Remote branch origin/$BRANCH not found" >&2; exit 4
fi
remote_sha="$(git rev-parse "refs/remotes/origin/$BRANCH")"
echo "Remote $BRANCH: $remote_sha"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  local_sha="$(git rev-parse "refs/heads/$BRANCH")"
  counts="$(git rev-list --left-right --count "refs/heads/$BRANCH...refs/remotes/origin/$BRANCH")"
  echo "Local  $BRANCH: $local_sha"
  echo "Ahead/behind local vs origin: $counts"
else
  echo "Local branch $BRANCH does not exist."
fi
if [[ "$MODE" == "status" ]]; then
  echo "STATUS ONLY: no local checkout or pull performed."
  exit 0
fi
if [[ "$BRANCH" == "main" && "${MOP_ALLOW_MAIN_SYNC:-0}" != "1" ]]; then
  echo "BLOCKED: main is protected. Use MOP_ALLOW_MAIN_SYNC=1 only after gate release." >&2
  exit 5
fi
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
else
  git switch --track -c "$BRANCH" "origin/$BRANCH"
fi
git merge --ff-only "origin/$BRANCH"
if [[ "$(git rev-parse HEAD)" != "$remote_sha" ]]; then
  echo "SYNC FAILED: HEAD does not match fetched origin/$BRANCH" >&2
  exit 6
fi
echo "SYNC OK: $(git rev-parse --short=12 HEAD) ($BRANCH)"
git status -sb
