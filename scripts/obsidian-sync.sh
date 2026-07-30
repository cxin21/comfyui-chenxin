#!/usr/bin/env bash
# obsidian-sync.sh — write a decision note to the user's Obsidian vault.
#
# Usage:
#   bash scripts/obsidian-sync.sh <event-name>
#
# Examples:
#   bash scripts/obsidian-sync.sh post-write-SPEC.md
#   bash scripts/obsidian-sync.sh post-write-plugin.json
#
# The vault path is hard-coded to D:/ObsidianWorkSpace/workspace per the
# global `~/.claude/rules/obsidian-workflow.md` rule. If the vault is
# missing, the script prints a warning and exits 0 (idempotent, non-fatal).
#
# Writes:
#   D:/ObsidianWorkSpace/workspace/00-Inbox/processed/decision-<YYYY-MM-DD>-<event>.md
#
# Tolerates missing vault (warns). Never fails the calling hook.

set -u

VAULT="${OBSIDIAN_VAULT_PATH:-D:/ObsidianWorkSpace/workspace}"
EVENT="${1:-unknown}"
TODAY="$(date +%Y-%m-%d)"

step() { printf "[obsidian-sync] %s\n" "$*"; }
warn() { printf "[obsidian-sync][warn] %s\n" "$*" >&2; }

INBOX="${VAULT}/00-Inbox/processed"
DST="${INBOX}/decision-${TODAY}-${EVENT}.md"

if [ ! -d "$VAULT" ]; then
  warn "vault not found at $VAULT — skipping sync (idempotent)."
  exit 0
fi

if [ ! -d "$INBOX" ]; then
  mkdir -p "$INBOX" || {
    warn "could not create $INBOX — skipping sync."
    exit 0
  }
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

# Defensive: refuse to write if $DST escaped $INBOX via symlink or
# parent-traversal attempts (post-tr sanitization should already prevent this).
case "$DST" in
  "$INBOX"/*) ;;
  *)
    warn "destination escaped inbox: $DST (event was: $EVENT_RAW)"
    exit 0
    ;;
esac

cat > "$DST" <<EOF
# ${EVENT}

- **date:** ${TODAY}
- **branch:** ${BRANCH}
- **trigger:** post-write hook (chenxin plugin)
- **event:** ${EVENT}

## What changed

A file in the alert list was written/edited:
- \`${EVENT}\`

## Why this note exists

Per the global \`obsidian-workflow\` rule, every change to \`SPEC.md\`,
\`plugin.json\`, or \`marketplace.json\` should leave a one-page trace in
the vault. This is that trace.

## Next action

Run \`/chenxin-review\` to confirm the change is internally consistent.
EOF

step "wrote $DST"
exit 0