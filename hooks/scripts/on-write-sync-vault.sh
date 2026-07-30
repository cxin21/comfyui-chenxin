#!/usr/bin/env bash
# on-write-sync-vault.sh — fired by hooks/hooks.json PostToolUse[Write|Edit].
#
# Detects whether the just-touched path is in the "alert list":
#   - SPEC.md
#   - .claude-plugin/plugin.json
#   - .claude-plugin/marketplace.json
#
# If yes, calls scripts/obsidian-sync.sh (which tolerates a missing vault
# and is itself idempotent — re-running on the same event yields the same
# note name).
#
# Stdin is the PostToolUse payload (JSON). We don't need to parse it for
# the alert-list check because the script also accepts --path <file> for
# dry-runs.

set -u

# Resolve the changed file from stdin payload OR env var override.
PATH_TOOL_INPUT="${CHENXIN_HOOK_PATH:-}"
if [ -z "$PATH_TOOL_INPUT" ] && [ ! -t 0 ]; then
  # Best-effort parse: grab the first file_path / path / file field.
  PATH_TOOL_INPUT="$(head -c 8192 <&0 | grep -oE '"(file_path|path|file)"[[:space:]]*:[[:space:]]*"[^"]+"' | head -n 1 | sed -E 's/.*"([^"]+)"$/\1/' || true)"
fi

if [ -z "${PATH_TOOL_INPUT:-}" ]; then
  exit 0
fi

# Normalize: strip leading "./", lowercase the basename for comparison.
BASENAME="$(echo "$PATH_TOOL_INPUT" | sed -E 's#^\./##' | xargs -I{} basename {})"

# Alert list — paths that should trigger obsidian-sync.sh.
case "$PATH_TOOL_INPUT" in
  *SPEC.md)                                  ALERT=1 ;;
  *.claude-plugin/plugin.json)               ALERT=1 ;;
  *.claude-plugin/marketplace.json)          ALERT=1 ;;
  *) ALERT=0 ;;
esac

if [ "$ALERT" -ne 1 ]; then
  exit 0
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SYNC="$REPO_ROOT/scripts/obsidian-sync.sh"

if [ ! -x "$SYNC" ] && [ ! -f "$SYNC" ]; then
  echo "[chenxin/hook] obsidian-sync.sh missing at $SYNC — skipping vault sync" >&2
  exit 0
fi

EVENT="post-write-$(echo "$BASENAME" | tr '/.' '-')"
echo "[chenxin/hook] vault sync triggered by: $BASENAME (event=$EVENT)" >&2
bash "$SYNC" "$EVENT" || true
exit 0