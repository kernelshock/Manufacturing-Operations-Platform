# MOP — local synchronization checkpoints (zrtserver)

**Scope:** FAIC Manufacturing Operations Platform. **Canonical repo:** `kernelshock/Manufacturing-Operations-Platform`. **Typical local checkout:** `~/dev/Manufacturing-Operations-Platform`.

## Required cadence

1. **Hito start:** check `origin`, current branch, local changes, ahead/behind and remote HEAD. Do not assume the user's machine has already synchronized.
2. **After each significant functional increment / PR update:** provide the user a concrete command to synchronize their local working branch and the exact expected remote commit.
3. **Before local validation / preview:** verify branch head equals the remote commit under test; run or instruct actual local checks against that SHA.
4. **Before gate acceptance:** confirm same-SHA CI evidence, operational/browser tests and no uncommitted local changes; record discrepancies explicitly.
5. **After authorized merge/release only:** sync local `main` with explicit opt-in. A draft PR, even with green CI, must not be treated as released.

## Safe tool included in repo

`infrastructure/scripts/local-sync-checkpoint.sh`

From the repository checkout, run:

```bash
bash infrastructure/scripts/local-sync-checkpoint.sh status feat/G6-materials
bash infrastructure/scripts/local-sync-checkpoint.sh sync feat/G6-materials
```

The tool checks the remote name, fetches remote references, prints current and remote SHAs, shows local changes and detects ahead/behind. `status` does not checkout or merge. `sync` stops if tracked/untracked local changes exist; it neither stashes, discards, commits nor rewrites anything. It switches to the requested branch and fast-forwards only; divergence is a hard stop. Existing work is never force-reset.

**Bootstrap exception:** If the script does not exist in an outdated local checkout, update with the conservative manual command (only when `git status --porcelain` shows no changes):

```bash
cd ~/dev/Manufacturing-Operations-Platform
git status -sb
git fetch origin --prune
git switch feat/G6-materials 2>/dev/null || git switch --track origin/feat/G6-materials
git merge --ff-only origin/feat/G6-materials
git log -1 --oneline
```

This fallback does not handle divergent branches. Stop and share terminal output rather than force-merge if commands fail.

`main` has an additional safeguard in the script: `MOP_ALLOW_MAIN_SYNC=1 bash infrastructure/scripts/local-sync-checkpoint.sh sync main` is allowed **only after a release has been explicitly authorized**.

## Interaction protocol

At each increment closeout, report (a) GitHub branch + verified remote SHA, (b) exact zrtserver sync command, (c) local sync result as **UNVERIFIED until user output or remote-machine execution confirms it**, (d) tests and gaps, and (e) explicit gate status. Never imply an assistant has run commands on zrtserver without an authorized connection and successful execution. Never auto-run a local sync from CI.

## G6.8 application

G6 remains draft/IN PROGRESS. Sync `feat/G6-materials`, not `main`. A successful GitHub commit or a green CI run does not prove the user's zrtserver checkout has been updated. Live local validation, comprehensive Materials browser fixtures and one-SHA G6 gate evidence remain separate acceptance obligations.
