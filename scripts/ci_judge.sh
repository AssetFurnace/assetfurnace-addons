#!/usr/bin/env bash
# The guard's decision for one pull request, used by both workflows. TRUSTED: runs from main, reads only data
# from the pull request (copied with `git archive`), never runs any of it.
# Usage: scripts/ci_judge.sh PR AUTHOR        Needs GH_TOKEN and BOT_LOGINS. Writes $RUNNER_TEMP/verdict.json.
set -euo pipefail
PR="$1"; AUTHOR="$2"; TMP="${RUNNER_TEMP:-/tmp}"
FILES=$(gh pr diff "$PR" --name-only | tr '\n' ' ')
LABELS=$(gh pr view "$PR" --json labels --jq '[.labels[].name] | join(",")')
CROSS=$(gh pr view "$PR" --json isCrossRepository --jq .isCrossRepository)
rm -rf "$TMP/head"; mkdir -p "$TMP/head"
git fetch --quiet origin "refs/pull/$PR/head"
git archive FETCH_HEAD addons pictures 2>/dev/null | tar -x -C "$TMP/head" || true
if [ "$CROSS" = "true" ] && [ "$(printf %s "${BOT_LOGINS:-}" | tr ',' '\n' | grep -cix "$AUTHOR" || true)" != "0" ]; then
  echo '{"action": "hold", "message": "This pull request comes from a fork, so a person has to look at it."}' > "$TMP/verdict.json"
else
  python scripts/guard_pr.py --author "$AUTHOR" --bots "${BOT_LOGINS:-}" --files "$FILES" --labels "$LABELS" --head "$TMP/head" > "$TMP/verdict.json"
fi
cat "$TMP/verdict.json"
jq -r .message "$TMP/verdict.json" > "$TMP/message.txt"
echo "action=$(jq -r .action "$TMP/verdict.json")" >> "${GITHUB_OUTPUT:-/dev/null}"
