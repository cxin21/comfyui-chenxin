#!/usr/bin/env bash
# on-session-start.sh — fired by hooks/hooks.json SessionStart[*].
#
# Prints a 20-line head of SPEC.md to stderr so the user (and Claude Code
# session-start context) can see the current phase + last-known status
# without opening the file.
#
# Stdout is untouched (Claude Code reads stdout for the hook result).
# Stderr is what the user sees in the session-start banner.

set -u

# Always run from the repo root so SPEC.md is found regardless of cwd.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

SPEC="$REPO_ROOT/SPEC.md"
if [ ! -f "$SPEC" ]; then
  echo "[chenxin/hook] no SPEC.md found at $SPEC — skipping head print." >&2
  exit 0
fi

echo "[chenxin/hook] === SPEC.md head ===" >&2
head -n 20 "$SPEC" >&2
echo "[chenxin/hook] ======================" >&2

# Print a one-line next-action hint.
NEXT_PHASE="$(grep -E '^- \[ \]' "$SPEC" | head -n 1 | awk '{print $3}' || true)"
if [ -n "${NEXT_PHASE:-}" ]; then
  echo "[chenxin/hook] next unchecked phase: $NEXT_PHASE  — invoke /chenxin-build to start" >&2
else
  echo "[chenxin/hook] no unchecked phases in SPEC.md" >&2
fi
exit 0