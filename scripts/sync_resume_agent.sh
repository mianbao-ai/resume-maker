#!/usr/bin/env bash
set -euo pipefail

# Pull the portable Resume Agent core from the experimental website repository.
# Usage: WEBSITE_REPO=../website ./scripts/sync_resume_agent.sh
WEBSITE_REPO="${WEBSITE_REPO:-../website}"
WEBSITE_REMOTE="${WEBSITE_REMOTE:-website}"
CORE_BRANCH="${CORE_BRANCH:-resume-agent-core}"
CORE_PREFIX="server/features/resume_agent/core"
TARGET_PREFIX="backend/app/resume_agent/core"

if ! git remote get-url "$WEBSITE_REMOTE" >/dev/null 2>&1; then
  git remote add "$WEBSITE_REMOTE" "git@github.com:mianbao-ai/website.git"
fi

git -C "$WEBSITE_REPO" fetch origin codex/resume-agent-core
git -C "$WEBSITE_REPO" subtree split --prefix="$CORE_PREFIX" -b "$CORE_BRANCH" >/dev/null
git -C "$WEBSITE_REPO" push origin "$CORE_BRANCH"
git fetch "$WEBSITE_REMOTE" "$CORE_BRANCH"
git subtree pull --prefix="$TARGET_PREFIX" "$WEBSITE_REMOTE" "$CORE_BRANCH" --squash

echo "Resume Agent core synced. Review the subtree commit, then run the backend tests."
