#!/usr/bin/env bash
# install.sh - Claude Code one-shot installer for comfyui-chenxin.
#
# Per P7 of the Skill-owned CLI / no-MCP plan, this script no longer
# touches $CODEX_HOME/config.toml and no longer stages a Codex plugin
# cache. It pip-installs each Skill and the comfyui-http-runtime
# transport in editable mode so the Claude Code marketplace plugin
# (`.claude-plugin/plugin.json`) resolves them on the next session.
#
# Usage:
#   bash scripts/install.sh
#
# Environment overrides:
#   PY=python3           which interpreter to use (default: first python3*)
#   SKIP_PROBE=1         skip the ComfyUI reachability probe
#
# Idempotent.

set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-}"
for cand in python python3 python3.11 python3.12; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "[install][error] python is required so the Skills can be pip-installed." >&2
  exit 1
fi

RELEASE_VERIFIER="$REPO_ROOT/scripts/verify_release.py"
[ -f "$RELEASE_VERIFIER" ] || { echo "[install][error] missing release verifier: $RELEASE_VERIFIER" >&2; exit 1; }

step() { printf "[install] %s\n" "$*"; }
warn() { printf "[install][warn] %s\n" "$*" >&2; }
die()  { printf "[install][error] %s\n" "$*" >&2; exit 1; }

if [ "${SKIP_PROBE:-}" != "1" ]; then
  if command -v curl >/dev/null 2>&1; then
    if ! curl -fsS --max-time 3 "http://127.0.0.1:8188/system_stats" >/dev/null 2>&1; then
      warn "ComfyUI at http://127.0.0.1:8188 did not respond (continuing)."
    fi
  elif command -v wget >/dev/null 2>&1; then
    if ! wget -q --timeout=3 -O- "http://127.0.0.1:8188/system_stats" >/dev/null 2>&1; then
      warn "ComfyUI at http://127.0.0.1:8188 did not respond (continuing)."
    fi
  else
    warn "No curl/wget; skipping ComfyUI reachability probe."
  fi
fi

step "verifying source tree"
"$PY" "$RELEASE_VERIFIER" --source-root "$REPO_ROOT" >/dev/null

step "pip-installing Skills + comfyui-http-runtime (editable)"
PKGS=(
  "$REPO_ROOT/runtime/comfyui_http"
  "$REPO_ROOT/skills/anima-prompt-v1"
  "$REPO_ROOT/skills/minimax-h3-prompt"
  "$REPO_ROOT/skills/camera-image"
  "$REPO_ROOT/skills/camera-video"
  "$REPO_ROOT/skills/camera-multiview"
)
for pkg in "${PKGS[@]}"; do
  if [ -f "$pkg/pyproject.toml" ]; then
    if ! "$PY" -m pip install -e "$pkg" --quiet 2>/dev/null; then
      die "pip install -e $pkg failed."
    fi
    step "pip-installed $pkg"
  else
    warn "skip $pkg (no pyproject.toml)"
  fi
done

step "DONE."
step "next: reload the Claude Code plugin (marketplace id: comfyui-chenxin)."
exit 0
