#!/usr/bin/env bash
# install.sh — one-shot installer for comfyui-chenxin on POSIX systems.
#
# Usage:
#   bash scripts/install.sh
#
# Does:
#   1. Registers the plugin in ~/.claude/settings.json under "plugins".
#      (Uses the same JSON-edit pattern as `Skill(update-config)`.)
#   2. Copies mcp/mcp_servers.json to ~/.claude/mcp_servers/comfyui-chenxin.json.
#   3. Prints /plugin install instructions for the user.
#
# Idempotent: re-running does not duplicate entries.

set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_HOME="${HOME}/.claude"
SETTINGS="${CLAUDE_HOME}/settings.json"
MCP_SRC="${REPO_ROOT}/mcp/mcp_servers.json"
MCP_DST_DIR="${CLAUDE_HOME}/mcp_servers"
MCP_DST="${MCP_DST_DIR}/comfyui-chenxin.json"

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

step() { printf "[install] %s\n" "$*"; }
warn() { printf "[install][warn] %s\n" "$*" >&2; }

# ----- 1. Register plugin ------------------------------------------------- #

if [ ! -d "$CLAUDE_HOME" ]; then
  warn "Claude home not found at $CLAUDE_HOME — creating it."
  mkdir -p "$CLAUDE_HOME"
fi

# Build the JSON via python (stdlib). Replaces only the "plugins" key, leaving
# everything else in settings.json untouched.
"$PY" - "$SETTINGS" << 'PYEOF'
import json
import sys

path = sys.argv[1]
data = {}
try:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
        if raw.strip():
            data = json.loads(raw)
except FileNotFoundError:
    pass
except json.JSONDecodeError as e:
    print(f"[install][warn] {path} is not valid JSON: {e}", file=sys.stderr)

plugins = data.get("plugins") or []
if not isinstance(plugins, list):
    plugins = []

# Idempotent: remove any prior entry with the same name.
plugins = [p for p in plugins if not (isinstance(p, dict) and p.get("name") == "comfyui-chenxin")]
plugins.append({
    "name": "comfyui-chenxin",
    "source": "github",
    "repo": "chenxin/comfyui-chenxin",
    "enabled": True,
})

data["plugins"] = plugins
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF

step "registered plugin in $SETTINGS"

# ----- 2. Copy MCP server config ------------------------------------------ #

if [ ! -f "$MCP_SRC" ]; then
  warn "mcp/mcp_servers.json not found at $MCP_SRC — skipping MCP install."
else
  mkdir -p "$MCP_DST_DIR"
  cp "$MCP_SRC" "$MCP_DST"
  step "copied $MCP_SRC -> $MCP_DST"
fi

# ----- 3. Install npm MCP driver (comfyui-mcp) ----------------------------- #
# The mcp/mcp_servers.json references `comfyui-mcp` from npm. We use `npx -y`
# to fetch on first invocation (no explicit global install needed), but
# we still try a global install to keep the experience offline-friendly.

if command -v npm >/dev/null 2>&1; then
  if npm ls -g comfyui-mcp >/dev/null 2>&1; then
    step "comfyui-mcp already installed globally"
  else
    step "installing comfyui-mcp via npm (global, may prompt for sudo)"
    npm install -g comfyui-mcp 2>&1 | tail -3 || warn "npm install -g comfyui-mcp failed (will fall back to npx on first use)"
  fi
else
  warn "npm not on PATH — the MCP server will still work via npx on first use, but global install skipped"
fi

# ----- 4. Next-action instructions ---------------------------------------- #

step "next: in Claude Code, run"
printf "         /plugin marketplace add cxin21/comfyui-chenxin\n"
printf "         /plugin install comfyui@chenxin\n"
printf "         /chenxin-init\n"
step "DONE."
exit 0