#!/usr/bin/env bash
# validate-plugin-schema.sh — JSON-schema-ish check on plugin manifests.
#
# Verifies:
#   1. .claude-plugin/plugin.json exists and parses as JSON.
#   2. plugin.name == "comfyui-chenxin".
#   3. plugin.commands / agents / hooks / mcpServers paths exist (relative
#      to repo root).
#   4. .claude-plugin/marketplace.json exists and parses as JSON.
#   5. marketplace.plugins[0].source.repo == "chenxin/comfyui-chenxin".
#
# Exit codes:
#   0   OK
#   1   file missing
#   2   JSON parse error
#   3   field missing
#   4   path does not exist

set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Pick a working Python (3.11+). Avoid `python3` on Windows where it's a
# Microsoft Store stub that exits 49 with no execution.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if command -v python >/dev/null 2>&1; then PY=python
  elif command -v python3.11 >/dev/null 2>&1; then PY=python3.11
  elif command -v python3 >/dev/null 2>&1; then PY=python3
  else PY=python
  fi
fi

step() { printf "[validate] %s\n" "$*"; }
fail() { printf "[validate][FAIL] %s\n" "$*" >&2; exit "${2:-1}"; }

PLUGIN_JSON="$REPO_ROOT/.claude-plugin/plugin.json"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"

[ -f "$PLUGIN_JSON" ] || fail "$PLUGIN_JSON missing" 1
[ -f "$MARKETPLACE_JSON" ] || fail "$MARKETPLACE_JSON missing" 1

"$PY" - "$REPO_ROOT" "$PLUGIN_JSON" "$MARKETPLACE_JSON" << 'PYEOF'
import json
import os
import sys

repo, plugin_path, market_path = sys.argv[1], sys.argv[2], sys.argv[3]

def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def fail(msg, code):
    print(f"[validate][FAIL] {msg}", file=sys.stderr)
    sys.exit(code)

# plugin.json
try:
    plugin = load(plugin_path)
except json.JSONDecodeError as e:
    fail(f"plugin.json is not valid JSON: {e}", 2)

if plugin.get("name") != "comfyui-chenxin":
    fail(f"plugin.name must be 'comfyui-chenxin', got '{plugin.get('name')}'", 3)

for key in ("commands", "agents", "hooks", "mcpServers"):
    rel = plugin.get(key)
    if not rel:
        fail(f"plugin.{key} missing", 3)
    abs_path = os.path.normpath(os.path.join(repo, rel))
    if not os.path.exists(abs_path):
        fail(f"plugin.{key} path does not exist: {rel} -> {abs_path}", 4)

print(f"[validate] plugin.json OK (name={plugin['name']})")

# marketplace.json
try:
    market = load(market_path)
except json.JSONDecodeError as e:
    fail(f"marketplace.json is not valid JSON: {e}", 2)

plugins = market.get("plugins") or []
if not plugins:
    fail("marketplace.plugins is empty", 3)

p0 = plugins[0]
if (p0.get("source") or {}).get("repo") != "chenxin/comfyui-chenxin":
    fail(f"marketplace.plugins[0].source.repo must be 'chenxin/comfyui-chenxin', got '{p0.get('source', {}).get('repo')}'", 3)

print(f"[validate] marketplace.json OK (repo={p0['source']['repo']})")
print("[validate] DONE.")
PYEOF

exit 0