#!/usr/bin/env bash
set -euo pipefail

# Pull the complete Resume Agent feature from the website repository.
# Usage: WEBSITE_REPO=../website ./scripts/sync_resume_agent.sh
WEBSITE_REPO="${WEBSITE_REPO:-../website}"
WEBSITE_REMOTE="${WEBSITE_REMOTE:-website}"
FEATURE_BRANCH="${FEATURE_BRANCH:-resume-maker}"
FEATURE_PREFIX="server/features/resume_agent"
TARGET_PREFIX="backend/app/resume_agent"

if ! git remote get-url "$WEBSITE_REMOTE" >/dev/null 2>&1; then
  git remote add "$WEBSITE_REMOTE" "git@github.com:mianbao-ai/website.git"
fi

git -C "$WEBSITE_REPO" fetch origin main
SPLIT_COMMIT="$(git -C "$WEBSITE_REPO" subtree split --prefix="$FEATURE_PREFIX" origin/main 2>/dev/null)"
git -C "$WEBSITE_REPO" branch -f "$FEATURE_BRANCH" "$SPLIT_COMMIT"
git -C "$WEBSITE_REPO" push --force-with-lease origin "$FEATURE_BRANCH"
git fetch "$WEBSITE_REMOTE" "$FEATURE_BRANCH"
git subtree pull --prefix="$TARGET_PREFIX" "$WEBSITE_REMOTE" "$FEATURE_BRANCH" --squash

echo "Resume Agent feature synced. Review the subtree commit, then run the backend tests."
