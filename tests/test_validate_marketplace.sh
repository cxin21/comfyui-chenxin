#!/usr/bin/env bash
# test_validate_marketplace.sh — Tier-1 validator coverage.
#
# scripts/validate-marketplace.sh is the strict JSON-schema check
# of .claude-plugin/marketplace.json. It was previously not exercised
# by ANY test (Explore agent's §9 finding #1).
#
# This test asserts:
#   1. Validator exits 0 against the live manifests (smoke)
#   2. Tamper test: a marketplace.json with a non-semver version
#      causes the validator to fail
#   3. Tamper test: a plugin name with invalid slug chars causes
#      failure
#   4. Tamper test: missing source.source field causes failure
#   5. Tamper test: cross-check failure (plugin name not in
#      marketplace.plugins[]) -> fail
#
# Avoids python3 -c inside $() capture (Git Bash pipe-closed issue).
# Uses pure bash + grep.
#
# Every assertion invokes the real validator — no mocking.
#
# Exit: 0 = all PASS, 1 = any FAIL.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pass() { printf '  [pass] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
FAILS=0

echo "=== Group 1 — happy path: validator against live manifests ==="

# 1a. scripts/validate-marketplace.sh exists and is executable
if [ -x scripts/validate-marketplace.sh ]; then
    pass "scripts/validate-marketplace.sh exists + is executable"
else
    fail "scripts/validate-marketplace.sh missing"
    exit 1
fi

# 1b. Validator passes against the live manifests
bash scripts/validate-marketplace.sh >/dev/null 2>&1
ec=$?
if [ "$ec" = "0" ]; then
    pass "validator exits 0 against live manifests"
else
    fail "validator failed on live manifests (ec=$ec)"
fi

echo
echo "=== Group 2 — tamper tests (each should fail) ==="

# Atomically swap marketplace.json with a tampered version and
# restore on EXIT.
ORIG=".claude-plugin/marketplace.json.bak-tamper-test"
if [ -f "$ORIG" ]; then rm -f "$ORIG"; fi
cp .claude-plugin/marketplace.json "$ORIG"
trap 'mv -f "$ORIG" .claude-plugin/marketplace.json 2>/dev/null' EXIT

# 2a. Tamper 1: non-semver version
cat > .claude-plugin/marketplace.json <<'JSON'
{
  "name": "comfyui-chenxin",
  "owner": {"name": "cxin21", "url": "https://github.com/cxin21/comfyui-chenxin"},
  "plugins": [
    {
      "name": "comfyui-chenxin",
      "source": {"source": "github", "repo": "cxin21/comfyui-chenxin"},
      "description": "tampered",
      "version": "not-semver-1234",
      "keywords": ["comfyui"]
    }
  ]
}
JSON
bash scripts/validate-marketplace.sh >/dev/null 2>&1
ec=$?
if [ "$ec" != "0" ]; then
    pass "non-semver version -> validator exits non-zero (ec=$ec)"
else
    fail "non-semver version PASSED (should have been rejected)"
fi

# 2b. Tamper 2: invalid plugin-name slug
cat > .claude-plugin/marketplace.json <<'JSON'
{
  "name": "comfyui-chenxin",
  "owner": {"name": "cxin21", "url": "https://github.com/cxin21/comfyui-chenxin"},
  "plugins": [
    {
      "name": "has spaces!",
      "source": {"source": "github", "repo": "cxin21/comfyui-chenxin"},
      "description": "tampered",
      "version": "1.0.0",
      "keywords": ["comfyui"]
    }
  ]
}
JSON
bash scripts/validate-marketplace.sh >/dev/null 2>&1
ec=$?
if [ "$ec" != "0" ]; then
    pass "plugin name with spaces -> validator exits non-zero (ec=$ec)"
else
    fail "plugin name with spaces PASSED (should have been rejected)"
fi

# 2c. Tamper 3: missing source.source field
cat > .claude-plugin/marketplace.json <<'JSON'
{
  "name": "comfyui-chenxin",
  "owner": {"name": "cxin21", "url": "https://github.com/cxin21/comfyui-chenxin"},
  "plugins": [
    {
      "name": "comfyui-chenxin",
      "source": {"repo": "cxin21/comfyui-chenxin"},
      "description": "tampered",
      "version": "1.0.0",
      "keywords": ["comfyui"]
    }
  ]
}
JSON
bash scripts/validate-marketplace.sh >/dev/null 2>&1
ec=$?
if [ "$ec" != "0" ]; then
    pass "missing source.source -> validator exits non-zero (ec=$ec)"
else
    fail "missing source.source PASSED (should have been rejected)"
fi

# 2d. Tamper 4: plugin name in source.repo doesn't match plugin name
cat > .claude-plugin/marketplace.json <<'JSON'
{
  "name": "comfyui-chenxin",
  "owner": {"name": "cxin21", "url": "https://github.com/cxin21/comfyui-chenxin"},
  "plugins": [
    {
      "name": "different-name",
      "source": {"source": "github", "repo": "cxin21/comfyui-chenxin"},
      "description": "tampered",
      "version": "1.0.0",
      "keywords": ["comfyui"]
    }
  ]
}
JSON
bash scripts/validate-marketplace.sh >/dev/null 2>&1
ec=$?
if [ "$ec" != "0" ]; then
    pass "plugin name != source.repo -> validator exits non-zero (ec=$ec)"
else
    fail "plugin name != source.repo PASSED (should have been rejected)"
fi

echo
if [ "$FAILS" -eq 0 ]; then
    echo "[validate-marketplace] all 6 assertions passed (1 happy + 1 existence + 4 tamper)"
    exit 0
else
    echo "[validate-marketplace] $FAILS assertion(s) failed"
    exit 1
fi
