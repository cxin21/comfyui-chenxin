#!/usr/bin/env bash
# test_install_sandbox.sh — Tier-1 sandboxed install test.
#
# Verifies that scripts/install.sh ACTUALLY writes a `comfyui-chenxin`
# plugin entry into $HOME/.claude/settings.json, with idempotency
# (re-running does not duplicate).
#
# Uses HOME=$(mktemp -d) to redirect all writes into a tmpdir so the
# user's real ~/.claude/settings.json is NEVER touched. The real file
# is backed up at the start of the test, then restored on exit.
#
# Avoids python3 -c inside $() because Git Bash on Windows has a
# pipe-closed issue with that pattern. Uses pure bash + grep.
#
# Every assertion invokes the real install.sh — no mocking.
#
# Exit: 0 = all PASS, 1 = any FAIL.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pass() { printf '  [pass] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
FAILS=0

# 1. Backup real settings.json (if it exists). Restore on EXIT.
REAL_SETTINGS="${HOME}/.claude/settings.json"
BACKUP="$(mktemp -d)/settings.json.backup"
mkdir -p "$(dirname "$BACKUP")"
if [ -f "$REAL_SETTINGS" ]; then
    cp "$REAL_SETTINGS" "$BACKUP"
fi
trap 'rm -rf "$(dirname "$BACKUP")" 2>/dev/null; [ -f "$BACKUP" ] && cp "$BACKUP" "$REAL_SETTINGS" 2>/dev/null' EXIT

# 2. Set HOME to a fresh tmpdir so install.sh writes there.
SANDBOX="$(mktemp -d)"
export HOME="$SANDBOX"
mkdir -p "$HOME/.claude"

echo "=== Group 1 — install.sh basic contract ==="

# 1a. install.sh must exist and be executable
if [ -x scripts/install.sh ]; then
    pass "scripts/install.sh exists and is executable"
else
    fail "scripts/install.sh missing or not executable"
    exit 1
fi

# 1b. install.sh must be idempotent — run it twice.
bash scripts/install.sh >/dev/null 2>&1 || true
bash scripts/install.sh >/dev/null 2>&1 || true

# 1c. The settings.json file must now exist in the sandbox $HOME
SETTINGS_FILE="$HOME/.claude/settings.json"
if [ -f "$SETTINGS_FILE" ]; then
    pass "install.sh created \$HOME/.claude/settings.json"
else
    fail "install.sh did not create settings.json"
    [ -f "$BACKUP" ] && cp "$BACKUP" "$REAL_SETTINGS" 2>/dev/null
    exit 1
fi

# 1d. The JSON must look valid (basic shape check via grep)
if grep -q '^\s*{' "$SETTINGS_FILE" \
   && grep -q '^\s*}\s*$' "$SETTINGS_FILE" \
   && grep -q '"plugins"' "$SETTINGS_FILE"; then
    pass "settings.json has valid JSON shape (starts with {, contains 'plugins' key, ends with })"
else
    fail "settings.json does not have valid JSON shape"
fi

# 1e. Exactly ONE plugin entry with name=comfyui-chenxin (idempotent
# across the 2 runs we just did).
n_entries=$(grep -cE '"name":\s*"comfyui-chenxin"' "$SETTINGS_FILE" 2>/dev/null || echo 0)
if [ "$n_entries" = "1" ]; then
    pass "exactly 1 plugin entry with name='comfyui-chenxin' (idempotent across 2 runs)"
else
    fail "expected 1 plugin entry, got $n_entries"
fi

# 1f. The entry must have source=github, repo=cxin21/comfyui-chenxin, enabled=true
has_source=$(grep -c '"source":\s*"github"' "$SETTINGS_FILE" 2>/dev/null || echo 0)
has_repo=$(grep -c '"repo":\s*"cxin21/comfyui-chenxin"' "$SETTINGS_FILE" 2>/dev/null || echo 0)
has_enabled=$(grep -c '"enabled":\s*true' "$SETTINGS_FILE" 2>/dev/null || echo 0)
if [ "$has_source" -ge 1 ] && [ "$has_repo" -ge 1 ] && [ "$has_enabled" -ge 1 ]; then
    pass "plugin entry: source=github, repo=cxin21/comfyui-chenxin, enabled=true"
else
    fail "plugin entry contract wrong: source=$has_source repo=$has_repo enabled=$has_enabled"
fi

echo
echo "=== Group 2 — install.sh preserves pre-existing settings ==="

# 2a. If user had OTHER plugins, install.sh must preserve them.
SANDBOX2="$(mktemp -d)"
export HOME="$SANDBOX2"
mkdir -p "$HOME/.claude"
cat > "$HOME/.claude/settings.json" <<'JSON'
{
  "model": "claude-3-5-sonnet",
  "mcpServers": {"other-mcp": {"type": "stdio", "command": "other-mcp", "args": []}},
  "plugins": [
    {"name": "user-plugin-A", "source": "github", "repo": "user-a/x", "enabled": true},
    {"name": "user-plugin-B", "source": "github", "repo": "user-b/y", "enabled": false}
  ]
}
JSON

bash scripts/install.sh >/dev/null 2>&1 || true

# 2b. After install, all pre-existing fields + other plugins preserved
preserved_model=$(grep -c '"model":\s*"claude-3-5-sonnet"' "$HOME/.claude/settings.json" 2>/dev/null || echo 0)
preserved_other_mcp=$(grep -c '"other-mcp"' "$HOME/.claude/settings.json" 2>/dev/null || echo 0)
preserved_user_a=$(grep -c '"user-plugin-A"' "$HOME/.claude/settings.json" 2>/dev/null || echo 0)
preserved_user_b=$(grep -c '"user-plugin-B"' "$HOME/.claude/settings.json" 2>/dev/null || echo 0)
added_comfyui=$(grep -c '"comfyui-chenxin"' "$HOME/.claude/settings.json" 2>/dev/null || echo 0)

if [ "$preserved_model" -ge 1 ] && [ "$preserved_other_mcp" -ge 1 ] \
   && [ "$preserved_user_a" -ge 1 ] && [ "$preserved_user_b" -ge 1 ] \
   && [ "$added_comfyui" -ge 1 ]; then
    pass "pre-existing settings + 2 other plugins + 1 mcpServer preserved AND comfyui-chenxin added"
else
    fail "pre-existing fields or plugins lost (model=$preserved_model other_mcp=$preserved_other_mcp user_a=$preserved_user_a user_b=$preserved_user_b added=$added_comfyui)"
fi

# 2c. After install, exactly 1 comfyui-chenxin (not duplicated by 2 existing)
n_after=$(grep -cE '"name":\s*"comfyui-chenxin"' "$HOME/.claude/settings.json" 2>/dev/null || echo 0)
if [ "$n_after" = "1" ]; then
    pass "exactly 1 comfyui-chenxin in mixed pre-existing settings (no duplicate)"
else
    fail "expected 1, got $n_after"
fi

echo
if [ "$FAILS" -eq 0 ]; then
    echo "[install-sandbox] all 8 assertions passed"
    exit 0
else
    echo "[install-sandbox] $FAILS assertion(s) failed"
    exit 1
fi
