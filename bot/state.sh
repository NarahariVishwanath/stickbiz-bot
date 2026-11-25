#!/usr/bin/env bash
# Keep each slot's working files on the "runs" branch so later workflows can continue the same Short.
#   bash bot/state.sh push <key>   # run/ (small files) -> runs branch: runs/<key>/
#   bash bot/state.sh pull <key>   # runs/<key>/ -> run/
set -euo pipefail
cmd="$1"; key="$2"
git config user.name  "stickbiz-bot"
git config user.email "stickbiz-bot@users.noreply.github.com"
rm -rf .state
if git ls-remote --exit-code --heads origin runs >/dev/null 2>&1; then
  git fetch -q origin runs
  git worktree add -q .state origin/runs
  (cd .state && git checkout -q -B runs)
else
  git worktree add -q --detach .state
  (cd .state && git checkout -q --orphan runs && git rm -rq --cached . && find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +)
fi
mkdir -p run
if [ "$cmd" = "push" ]; then
  mkdir -p ".state/runs/$key"
  for f in run/*.json run/*.md run/*.txt; do [ -e "$f" ] && cp "$f" ".state/runs/$key/"; done
  (cd .state && git add -A "runs/$key" && (git commit -qm "state $key" || true) && git push -q origin runs)
  echo "state saved: runs/$key"
else
  cp -r ".state/runs/$key/." run/
  echo "state loaded: runs/$key"
fi
git worktree remove --force .state
