#!/usr/bin/env bash
# The guard's decision for one pull request, used by both workflows. TRUSTED: runs from main, reads only data
# from the pull request (copied with `git archive`), never runs any of it.
# Usage: scripts/ci_judge.sh PR AUTHOR [EXPECTED_SHA]
#   Needs GH_TOKEN, GITHUB_REPOSITORY and BOT_LOGINS (GUARD_OFFLINE=1 skips the network check of addon.json, for tests). Writes $RUNNER_TEMP/verdict.json (and message.txt).
#   With EXPECTED_SHA, the pull request must still be at exactly that commit, or the verdict is "hold".
set -euo pipefail
PR="$1"; AUTHOR="$2"; EXPECT="${3:-}"; TMP="${RUNNER_TEMP:-/tmp}"
# every file the pull request touches, AND the old name of a renamed file, so a rename cannot hide a deletion
FILES=$(gh api --paginate "repos/$GITHUB_REPOSITORY/pulls/$PR/files" --jq '.[] | .filename, (.previous_filename // empty)' | tr '\n' ' ')
CROSS=$(gh pr view "$PR" --json isCrossRepository --jq .isCrossRepository)
BASE=$(gh pr view "$PR" --json baseRefName --jq .baseRefName)
rm -rf "$TMP/head"; mkdir -p "$TMP/head"
git fetch --quiet origin "refs/pull/$PR/head"
GOT=$(git rev-parse FETCH_HEAD)
git archive "$GOT" addons pictures 2>/dev/null | tar -x -C "$TMP/head" || true
if [ -n "$EXPECT" ] && [ "$GOT" != "$EXPECT" ]; then
  echo '{"action": "hold", "message": "The pull request changed after it was checked."}' > "$TMP/verdict.json"
elif [ "$BASE" != "main" ]; then
  echo '{"action": "hold", "message": "This pull request is not aimed at main, so a person has to look at it."}' > "$TMP/verdict.json"
elif [ "$CROSS" = "true" ] && [ "$(printf %s "${BOT_LOGINS:-}" | tr ',' '\n' | grep -cix "$AUTHOR" || true)" != "0" ]; then
  echo '{"action": "hold", "message": "This pull request comes from a fork, so a person has to look at it."}' > "$TMP/verdict.json"
else
  python scripts/guard_pr.py --author "$AUTHOR" --bots "${BOT_LOGINS:-}" --files "$FILES" --head "$TMP/head" ${GUARD_OFFLINE:+--offline} > "$TMP/verdict.json"
fi
cat "$TMP/verdict.json"
jq -r .message "$TMP/verdict.json" > "$TMP/message.txt"
echo "action=$(jq -r .action "$TMP/verdict.json")" >> "${GITHUB_OUTPUT:-/dev/null}"
