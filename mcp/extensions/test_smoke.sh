#!/usr/bin/env bash
# test_smoke.sh — minimal sanity test for the four P0.2 MCP-augmenting CLIs.
#
# Runs each tool with `--help` (and a non-network dry probe where useful)
# and asserts exit code 0. Does NOT require a real ComfyUI server, a real
# hardware profile, or a real templates index. Designed to be runnable in
# isolation during adversarial review.
#
# Usage:
#   bash mcp/extensions/test_smoke.sh
#
# Exit codes:
#   0   all tools passed
#   non-zero   first failing tool's exit code

set -u

cd "$(dirname "$0")/../.."  # repo root

FAIL=0
PASS=0

# Each test is: <name> <command...>
run() {
  local name="$1"; shift
  local out
  out="$("$@" 2>&1)"
  local code=$?
  if [ "$code" -eq 0 ]; then
    printf "  [pass] %s\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "  [FAIL] %s (exit=%d)\n%s\n" "$name" "$code" "$out"
    FAIL=$((FAIL + 1))
  fi
}

echo "[smoke] P0.2 mcp/extensions sanity test"
echo "[smoke] cwd: $(pwd)"
echo "[smoke] python: $(python --version 2>&1)"

PY=python
[ -n "${PYTHON:-}" ] && PY="$PYTHON"

echo
echo "[smoke] 1) each CLI must respond to --help with exit 0"
run "auto_launch --help"     "$PY" mcp/extensions/auto_launch.py --help
run "vram_decide --help"     "$PY" mcp/extensions/vram_decide.py --help
run "template_get --help"    "$PY" mcp/extensions/template_get.py --help
run "gui_save --help"        "$PY" mcp/extensions/gui_save.py --help

echo
echo "[smoke] 2) each CLI must reject bogus args with exit 2 (usage error)"
run_bogus() {
  local name="$1"; shift
  local out
  out="$("$@" 2>&1)"
  local code=$?
  if [ "$code" -eq 2 ]; then
    printf "  [pass] %s (exit=2 as expected)\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "  [FAIL] %s (expected exit=2, got %d)\n%s\n" "$name" "$code" "$out"
    FAIL=$((FAIL + 1))
  fi
}
run_bogus "vram_decide missing --vram"   "$PY" mcp/extensions/vram_decide.py --model anima
run_bogus "vram_decide bad --vram=0"     "$PY" mcp/extensions/vram_decide.py --vram 0 --model anima
run_bogus "template_get bad --limit=999" "$PY" mcp/extensions/template_get.py --limit 999
run_bogus "gui_save missing --graph"     "$PY" mcp/extensions/gui_save.py --name foo
run_bogus "gui_save missing --name"      "$PY" mcp/extensions/gui_save.py --graph -

echo
echo "[smoke] 3) friendly probes that exercise real code paths but need no ComfyUI"
echo "    (each must emit valid JSON on stdout and exit 0)"

probe_json() {
  local name="$1"; shift
  local out
  out="$("$@" 2>/dev/null)"
  local code=$?
  if [ "$code" -eq 0 ] && printf '%s' "$out" | python -c "import sys,json; json.loads(sys.stdin.read())" >/dev/null 2>&1; then
    printf "  [pass] %s\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "  [FAIL] %s (exit=%d, json-parse failed)\noutput: %s\n" "$name" "$code" "$out"
    FAIL=$((FAIL + 1))
  fi
}

probe_json "auto_launch --no-launch" \
  "$PY" mcp/extensions/auto_launch.py --no-launch --timeout 2 --poll 0.5

probe_json "vram_decide --vram 8 --model anima" \
  "$PY" mcp/extensions/vram_decide.py --vram 8 --model anima

probe_json "vram_decide --vram 8 --model __nonexistent" \
  "$PY" mcp/extensions/vram_decide.py --vram 8 --model __nonexistent

probe_json "template_get --use-case txt2img --modality image" \
  "$PY" mcp/extensions/template_get.py --use-case txt2img --modality image

# gui_save writes a real workflow into <ComfyUI>/user/default/workflows/.
# That is a side effect on the user's ComfyUI install, so we ONLY do it when
# the operator explicitly opts in via CHENXIN_SMOKE_WRITE_REAL=1. Default
# runs skip this probe so the smoke test stays zero-side-effect on a real
# install.
if [ "${CHENXIN_SMOKE_WRITE_REAL:-0}" = "1" ] && [ -d "${COMFYUI_PATH:-$HOME/ComfyUI}" ]; then
  tmpgraph="$(mktemp -t chenxin_smoke_graph.XXXXXX.json)"
  printf '{"nodes":[],"links":[],"groups":[],"config":{},"extra":{},"version":0.4}' > "$tmpgraph"
  probe_json "gui_save with tmp graph" \
    "$PY" mcp/extensions/gui_save.py --graph "$tmpgraph" --name chenxin_smoke_test
  rm -f "$tmpgraph"
else
  printf "  [skip] gui_save probe (set CHENXIN_SMOKE_WRITE_REAL=1 to enable writes into a real ComfyUI dir)\n"
fi

echo
echo "[smoke] summary: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]