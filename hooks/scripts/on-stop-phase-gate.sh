#!/usr/bin/env bash
# on-stop-phase-gate.sh — fired by hooks/hooks.json Stop[*].
#
# If the current git branch looks like a phase/PX.Y branch AND there are
# uncommitted changes, print a PR-template-friendly reminder to stderr.
#
# This is a hint, not a gate — Stop hooks cannot block (only PreToolUse can).
# The actual gate is in the orchestrator + reviewer protocol.

set -u

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"

# Only fire on phase/PX.Y branches.
case "$BRANCH" in
  phase/*) ;;
  *) exit 0 ;;
esac

# Check for dirty state.
if git diff --quiet && git diff --cached --quiet; then
  # Clean — nothing to remind.
  exit 0
fi

echo "[chenxin/hook] phase branch '$BRANCH' has uncommitted changes." >&2
echo "[chenxin/hook] next action: review the diff, run /chenxin-review, then /chenxin-build." >&2
echo "[chenxin/hook] PR title convention: feat(<scope>): <phase-id> <short description>" >&2
exit 0