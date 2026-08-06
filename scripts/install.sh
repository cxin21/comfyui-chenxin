#!/usr/bin/env bash
# install.sh - one-shot installer for comfyui-chenxin on POSIX systems.
#
# Registers the plugin + comfyui-mcp MCP server for Claude Code and Codex,
# installs the plugin into Codex's plugin cache, and verifies that the MCP
# server actually starts and exposes the tools the runtime needs.
#
# Usage:
#   bash scripts/install.sh                                # npx mode (portable default)
#   MODE=local LOCAL_CLONE_PATH=/path/to/comfyui-mcp bash scripts/install.sh
#
# Environment overrides:
#   MODE=npx|local           (default npx)
#   PACKAGE_VERSION=0.41.0
#   COMFY_URL=http://127.0.0.1:8188
#   LOCAL_CLONE_PATH=<path>  (required when MODE=local)
#   CLAUDE_HOME=$HOME/.claude
#   CODEX_HOME=$HOME/.codex
#   SKIP_CLAUDE=1  SKIP_CODEX=1  SKIP_VERIFY=1
#
# Idempotent. Re-running replaces existing registrations; Codex side keeps a
# timestamped backup of config.toml.

set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${MODE:-npx}"
PACKAGE_VERSION="${PACKAGE_VERSION:-0.41.0}"
COMFY_URL="${COMFY_URL:-http://127.0.0.1:8188}"
LOCAL_CLONE_PATH="${LOCAL_CLONE_PATH:-}"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

# Pick a working Python (3.10+).
PY=""
for cand in python python3 python3.11 python3.12; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "[install][error] python is required for the Codex TOML edits and verification." >&2
  exit 1
fi

step() { printf "[install] %s\n" "$*"; }
warn() { printf "[install][warn] %s\n" "$*" >&2; }
die()  { printf "[install][error] %s\n" "$*" >&2; exit 1; }

# ---------- 0. Resolve MCP launch spec ----------
case "$MODE" in
  npx)
    command -v npx >/dev/null 2>&1 || die "Mode=npx requires npx on PATH."
    LAUNCH_CMD="npx"
    LAUNCH_ARGS=( "-y" "comfyui-mcp@${PACKAGE_VERSION}" "--full" "--comfyui-url" "$COMFY_URL" )
    ;;
  local)
    [ -n "$LOCAL_CLONE_PATH" ] || die "MODE=local requires LOCAL_CLONE_PATH."
    DIST="$LOCAL_CLONE_PATH/dist/index.js"
    [ -f "$DIST" ] || die "Local clone build not found at $DIST."
    command -v node >/dev/null 2>&1 || die "node is required for MODE=local."
    LAUNCH_CMD="node"
    LAUNCH_ARGS=( "$DIST" "--full" "--comfyui-url" "$COMFY_URL" )
    ;;
  *) die "Unknown MODE=$MODE (use npx or local)." ;;
esac

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS --max-time 3 "$COMFY_URL/system_stats" >/dev/null 2>&1; then
    warn "ComfyUI at $COMFY_URL did not respond (continuing; server will be verified separately)."
  fi
elif command -v wget >/dev/null 2>&1; then
  if ! wget -q --timeout=3 -O- "$COMFY_URL/system_stats" >/dev/null 2>&1; then
    warn "ComfyUI at $COMFY_URL did not respond."
  fi
else
  warn "No curl/wget; skipping ComfyUI reachability probe."
fi

# ---------- 1. Claude Code ----------
if [ "${SKIP_CLAUDE:-}" != "1" ]; then
  step "Claude Code: registering plugin + copying MCP config"
  mkdir -p "$CLAUDE_HOME"
  SETTINGS="$CLAUDE_HOME/settings.json"

  "$PY" - "$SETTINGS" << 'PYEOF'
import json, sys
path = sys.argv[1]
data = {}
try:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
        if raw.strip():
            data = json.loads(raw)
except (FileNotFoundError, json.JSONDecodeError):
    pass
plugins = data.get("plugins") or []
if not isinstance(plugins, list):
    plugins = []
plugins = [p for p in plugins if not (isinstance(p, dict) and p.get("name") == "comfyui-chenxin")]
plugins.append({"name": "comfyui-chenxin", "source": "github", "repo": "cxin21/comfyui-chenxin", "enabled": True})
data["plugins"] = plugins
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF
  step "registered plugin in $SETTINGS"

  MCP_SRC="$REPO_ROOT/mcp/mcp_servers.json"
  MCP_DST_DIR="$CLAUDE_HOME/mcp_servers"
  MCP_DST="$MCP_DST_DIR/comfyui-chenxin.json"
  if [ -f "$MCP_SRC" ]; then
    mkdir -p "$MCP_DST_DIR"
    cp "$MCP_SRC" "$MCP_DST"
    step "copied $MCP_SRC -> $MCP_DST"
  else
    warn "mcp/mcp_servers.json not found; skipping Claude MCP file copy."
  fi
fi

# ---------- 2. Codex: MCP + plugin cache ----------
if [ "${SKIP_CODEX:-}" != "1" ]; then
  step "Codex: writing [mcp_servers.comfyui-mcp] into config.toml"
  CONFIG="$CODEX_HOME/config.toml"
  if [ -f "$CONFIG" ]; then
    TS=$(date +%Y%m%d%H%M%S)
    BACKUP="$CONFIG.bak-comfyui-chenxin-$TS"
    cp "$CONFIG" "$BACKUP"
    step "backed up $CONFIG -> $BACKUP"
  fi

  ARGS_FOR_PY="$("$PY" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "${LAUNCH_ARGS[@]}")"

  "$PY" - "$CONFIG" "$LAUNCH_CMD" "$ARGS_FOR_PY" << 'PYEOF'
import json, sys
path = sys.argv[1]
cmd = sys.argv[2]
args = json.loads(sys.argv[3])

lines = []
try:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
except FileNotFoundError:
    pass

def quote_toml_string(s):
    return '"' + s.replace("\\", "\\\\").replace("\"", "\\\"") + '"'

args_str = ", ".join(quote_toml_string(a) for a in args)
block = [
    "[mcp_servers.comfyui-mcp]",
    "type = \"stdio\"",
    f"command = {quote_toml_string(cmd)}",
    f"args = [{args_str}]",
]

out = []
skipping = False
replaced = False
for line in lines:
    t = line.strip()
    if t.startswith("[") and t.endswith("]"):
        if skipping:
            skipping = False
        if t == "[mcp_servers.comfyui-mcp]":
            out.extend(block)
            replaced = True
            skipping = True
            continue
    if not skipping:
        out.append(line)
if not replaced:
    if out and out[-1] != "":
        out.append("")
    out.extend(block)

with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
PYEOF
  step "wrote MCP block to $CONFIG"

  step "Codex: installing plugin into plugin cache"
  PLUGIN_JSON="$REPO_ROOT/.codex-plugin/plugin.json"
  [ -f "$PLUGIN_JSON" ] || die "Missing $PLUGIN_JSON."

  VERSION="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["version"])' "$PLUGIN_JSON")"
  [ -n "$VERSION" ] || die "plugin.json has no version."

  CACHE_ROOT="$CODEX_HOME/plugins/cache/personal/comfyui-chenxin"
  STAGING="${TMPDIR:-/tmp}/comfyui-chenxin-install-$VERSION"
  rm -rf "$STAGING"
  mkdir -p "$STAGING"

  for entry in "skills" ".codex-plugin" ".mcp.json" "LICENSE" "README.md"; do
    src="$REPO_ROOT/$entry"
    if [ -e "$src" ]; then
      cp -R "$src" "$STAGING/$entry"
    fi
  done

  [ -f "$STAGING/.codex-plugin/plugin.json" ] || die "Staged plugin.json missing."
  STAGED_VERSION="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["version"])' "$STAGING/.codex-plugin/plugin.json")"
  [ "$STAGED_VERSION" = "$VERSION" ] || die "Staged version [$STAGED_VERSION] does not match directory version [$VERSION]."
  [ -d "$STAGING/skills" ] || die "Staged skills/ missing."

  mkdir -p "$CACHE_ROOT"
  case "$(cd "$(dirname "$CACHE_ROOT")" && pwd)" in
    "$(cd "$CODEX_HOME" && pwd)") ;;
    *) die "Refusing to operate on a CACHE_ROOT outside CODEX_HOME: $CACHE_ROOT" ;;
  esac
  for dir in "$CACHE_ROOT"/*; do
    [ -d "$dir" ] || continue
    step "removing previous version directory $dir"
    rm -rf "$dir"
  done
  TARGET="$CACHE_ROOT/$VERSION"
  mv "$STAGING" "$TARGET"
  step "installed plugin at $TARGET"

  for rel in "skills/character-video-pipeline/SKILL.md" "skills/character-video-pipeline/runtime/capabilities.py"; do
    cache_file="$TARGET/$rel"
    repo_file="$REPO_ROOT/$rel"
    if [ -f "$cache_file" ] && [ -f "$repo_file" ]; then
      cache_hash="$("$PY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:16])' "$cache_file")"
      repo_hash="$("$PY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:16])' "$repo_file")"
      match="MATCH"; [ "$cache_hash" = "$repo_hash" ] || match="DIFFER"
      step "$rel cache=$cache_hash repo=$repo_hash [$match]"
    fi
  done
fi

# ---------- 3. Verification ----------
if [ "${SKIP_VERIFY:-}" != "1" ]; then
  step "Verifying MCP handshake (command=$LAUNCH_CMD)"
  ARGS_JSON="$("$PY" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "${LAUNCH_ARGS[@]}")"
  if printf '%s' "$ARGS_JSON" | "$PY" "$REPO_ROOT/scripts/verify_mcp.py" --command "$LAUNCH_CMD" --timeout 180; then
    step "MCP handshake OK; all required tools present."
  else
    rc=$?
    if [ "$rc" = "1" ]; then
      die "MCP handshake started but the server is missing required tools (see JSON above)."
    else
      die "MCP server failed to start or did not answer the handshake (see JSON above)."
    fi
  fi
fi

step "DONE."
step "next: restart the Codex desktop app (or open a new task) so it picks up the new MCP server."
exit 0
