#!/usr/bin/env bash
# bootstrap.sh — after install, ensure ComfyUI is up and print machine-block.
#
# Usage:
#   bash scripts/bootstrap.sh
#
# Does:
#   1. Calls python mcp/extensions/auto_launch.py (idempotent: skips launch
#      if ComfyUI is already up).
#   2. Calls python mcp/extensions/vram_decide.py once for each top model
#      and prints the "machine block" (recommended quant + sampler).
#
# Exit codes:
#   0   all OK
#   1   ComfyUI unreachable
#   2   vram_decide error
#   3   internal missing-file

set -u

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

step() { printf "[bootstrap] %s\n" "$*"; }
warn() { printf "[bootstrap][warn] %s\n" "$*" >&2; }
fail() { printf "[bootstrap][FAIL] %s\n" "$*" >&2; exit "${2:-1}"; }

# ----- 1. ComfyUI up? ----------------------------------------------------- #

if [ ! -f "$REPO_ROOT/mcp/extensions/auto_launch.py" ]; then
  fail "mcp/extensions/auto_launch.py missing" 3
fi

step "checking ComfyUI on :8188 …"
if ! "$PY" "$REPO_ROOT/mcp/extensions/auto_launch.py" --no-launch --timeout 5 >/dev/null 2>&1; then
  step "ComfyUI is down — attempting auto-launch"
  if ! "$PY" "$REPO_ROOT/mcp/extensions/auto_launch.py" --timeout 60; then
    fail "ComfyUI unreachable on :8188 — start it manually: python -m comfyui.cmd.main --listen 127.0.0.1 --port 8188 --gpu-only" 1
  fi
fi

step "ComfyUI is up"

# ----- 2. Machine block --------------------------------------------------- #

if [ ! -f "$REPO_ROOT/mcp/extensions/vram_decide.py" ]; then
  fail "mcp/extensions/vram_decide.py missing" 3
fi

# Probe VRAM via the system_stats endpoint (best effort; ignore failures).
VRAM="8"
PROBE_OUT="$("$PY" -c '
import json, sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3) as r:
        d = json.load(r)
        for dev in d.get("devices", []):
            total = dev.get("vram_total", 0)
            for n in (8, 12, 16, 24):
                if total <= n * 1024 * 1024 * 1024 * 1.1:
                    print(n)
                    sys.exit(0)
            print(int(total / (1024 ** 3)))
            sys.exit(0)
    print("8")
except Exception:
    print("8")
' 2>/dev/null)"
if [ -n "$PROBE_OUT" ]; then
  VRAM="$PROBE_OUT"
fi

step "machine block (VRAM=${VRAM}GB):"
for MODEL in anima wan sdxl flux; do
  printf "  %-8s -> " "$MODEL"
  "$PY" "$REPO_ROOT/mcp/extensions/vram_decide.py" --vram "$VRAM" --model "$MODEL" 2>/dev/null \
    | "$PY" -c "import sys,json; d=json.load(sys.stdin); print(f\"quant={d.get('quant','?')} swap={d.get('swap_blocks','?')} blocked={d.get('blocked',False)}\")" \
    || printf "ERR"
done

step "DONE."
exit 0