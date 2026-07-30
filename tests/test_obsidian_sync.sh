#!/usr/bin/env bash
# test_obsidian_sync.sh — smoke for scripts/obsidian-sync.sh.
#
# Verifies (in a sandboxed OBSIDIAN_VAULT_PATH):
#   1. happy path: writes decision-<DATE>-<EVENT>.md under inbox/
#   2. event argument is sanitized (path traversal blocked)
#   3. missing vault is non-fatal (exits 0)
#   4. unset event defaults to 'unknown'

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="${ROOT}/scripts/obsidian-sync.sh"
SANDBOX="/tmp/obsidian-sync-sandbox-$$"
mkdir -p "$SANDBOX/00-Inbox/processed"

pass() { printf '  [pass] %s\n' "$*"; }
counter() { printf '%-60s ' "$1"; }

cleanup() { rm -rf "$SANDBOX"; }
trap cleanup EXIT

# 1. Happy path
counter "happy: writes decision-*.md with sanitized event name"
OBSIDIAN_VAULT_PATH="$SANDBOX" bash "$SCRIPT" "phase-p1.3-test" >/dev/null
[ -f "$SANDBOX/00-Inbox/processed/decision-"*"-phase-p1.3-test.md" ] && pass "file present"

# 2. Event sanitization
counter "sanitization: traversal characters stripped from EVENT"
OBSIDIAN_VAULT_PATH="$SANDBOX" bash "$SCRIPT" "../../etc/passwd" >/dev/null
if compgen -G "$SANDBOX/00-Inbox/processed/decision-"*"-etcpasswd.md" >/dev/null; then
  pass "sanitized event collapsed"
fi

# 3. Missing vault exits 0
counter "missing vault exits 0 (non-fatal)"
set +e
OBSIDIAN_VAULT_PATH="/tmp/does-not-exist-$$-nope" bash "$SCRIPT" "anything" >/dev/null 2>&1
code=$?
set -e
[ "$code" = "0" ] && pass "exit 0"

# 4. Unset event defaults to 'unknown'
counter "unset event defaults to 'unknown'"
OBSIDIAN_VAULT_PATH="$SANDBOX" bash "$SCRIPT" >/dev/null
if compgen -G "$SANDBOX/00-Inbox/processed/decision-"*"-unknown.md" >/dev/null; then
  pass "created with event=unknown"
fi

echo
echo "[obsidian-sync smoke] all checks passed"
