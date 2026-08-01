#!/usr/bin/env bash
# bootstrap.sh — after install, ensure ComfyUI is up and print machine-block.
#
# Usage:
#   bash scripts/bootstrap.sh
#
# Does:
#   1. Probe http://127.0.0.1:8188/system_stats; if down, spawn
#      `python -m comfyui.cmd.main --listen 127.0.0.1 --port 8188 --gpu-only`
#      as a detached subprocess and wait for readiness (max 60s).
#   2. For each top model (anima, wan, sdxl, flux), read
#      skills/prompt-forge/hardware/<vram>.json (or <vram>gb.json) and
#      print the recommended quant + sampler block.
#
# The two responsibilities were formerly mcp/extensions/auto_launch.py and
# mcp/extensions/vram_decide.py; they were inlined here in 2026-08 to drop the
# stdlib CLI layer (see CHANGELOG "Refactor: remove mcp/extensions/").
#
# Exit codes:
#   0   all OK
#   1   ComfyUI unreachable
#   2   hardware probe error

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

STATS_URL="http://127.0.0.1:8188/system_stats"

# ----- 1. ComfyUI up? (inlined from former auto_launch.py) ----------------- #

step "checking ComfyUI on :8188 …"

# 1a. Probe /system_stats; emit "up" or "down".
PROBE_OUT="$("$PY" -c "
import urllib.request, sys
try:
    with urllib.request.urlopen(\"$STATS_URL\", timeout=3) as r:
        if r.status == 200:
            print(\"up\"); sys.exit(0)
except Exception:
    pass
print(\"down\")
" 2>/dev/null)"

if [ "$PROBE_OUT" = "down" ]; then
  step "ComfyUI is down — attempting auto-launch"

  # 1b. Spawn detached: CREATE_NEW_PROCESS_GROUP on Windows, start_new_session on POSIX.
  if ! "$PY" -c "
import os, subprocess, sys
kwargs = {}
if os.name == \"nt\":
    kwargs[\"creationflags\"] = subprocess.CREATE_NEW_PROCESS_GROUP
else:
    kwargs[\"start_new_session\"] = True
subprocess.Popen(
    [sys.executable, \"-m\", \"comfyui.cmd.main\",
     \"--listen\", \"127.0.0.1\", \"--port\", \"8188\", \"--gpu-only\"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs,
)
" 2>&1; then
    fail "failed to spawn ComfyUI" 1
  fi

  # 1c. Wait up to 60s for port bind + /system_stats 200.
  READY="$("$PY" -c "
import socket, time, urllib.request
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    try:
        with socket.create_connection((\"127.0.0.1\", 8188), timeout=1):
            try:
                with urllib.request.urlopen(\"$STATS_URL\", timeout=2) as r:
                    if r.status == 200:
                        print(\"ready\"); sys.exit(0)
            except Exception:
                pass
    except OSError:
        pass
    time.sleep(1)
print(\"timeout\")
" 2>/dev/null)"
  if [ "$READY" != "ready" ]; then
    fail "ComfyUI unreachable on :8188 — start it manually: python -m comfyui.cmd.main --listen 127.0.0.1 --port 8188 --gpu-only" 1
  fi
  step "ComfyUI ready"
else
  step "ComfyUI is up"
fi

# ----- 2. Probe VRAM (existing inline pattern, unchanged) ------------------ #

VRAM="$("$PY" -c '
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

# ----- 3. Machine block (inlined from former vram_decide.py) --------------- #
# Reads hardware/<vram>.json (preferred) or <vram>gb.json (legacy) and emits
# {quant, swap_blocks, sampler_defaults, blocked, reason}. Three graceful
# degradation paths: profile missing / model not listed / entry malformed —
# all yield blocked=true with a human-readable reason.

step "machine block (VRAM=${VRAM}GB):"
for MODEL in anima wan sdxl flux; do
  printf "  %-8s -> " "$MODEL"

  RESULT="$("$PY" -c "
import json, sys
from pathlib import Path
root = Path(\"$REPO_ROOT\") / \"skills\" / \"prompt-forge\" / \"hardware\"
vram = $VRAM
candidates = [root / f\"{vram}.json\", root / f\"{vram}gb.json\"]
profile = {}
for p in candidates:
    if p.exists():
        try:
            with p.open(\"r\", encoding=\"utf-8\") as f:
                profile = json.load(f)
            break
        except Exception:
            pass
models = profile.get(\"models\", {}) if isinstance(profile, dict) else {}
DEFAULT = {\"sampler\": \"euler\", \"scheduler\": \"normal\", \"steps\": 25, \"cfg\": 5.5}
model = \"$MODEL\"
if model not in models:
    print(json.dumps({
        \"quant\": \"\", \"swap_blocks\": 0, \"sampler_defaults\": {},
        \"blocked\": True,
        \"reason\": f\"model '{model}' not listed in hardware/{vram}.json; consult recipes/MODELS.md\",
    }))
    sys.exit(0)
entry = models[model]
if not isinstance(entry, dict):
    print(json.dumps({
        \"quant\": \"\", \"swap_blocks\": 0, \"sampler_defaults\": {},
        \"blocked\": True, \"reason\": f\"hardware entry for '{model}' is malformed\",
    }))
    sys.exit(0)
sampler = entry.get(\"sampler_defaults\") or DEFAULT
if not isinstance(sampler, dict):
    sampler = DEFAULT
print(json.dumps({
    \"quant\": str(entry.get(\"quant\", \"fp16\")),
    \"swap_blocks\": int(entry.get(\"swap_blocks\", 0)),
    \"sampler_defaults\": sampler,
    \"blocked\": bool(entry.get(\"blocked\", False)),
    \"reason\": str(entry.get(\"reason\", f\"{vram} GB VRAM fits '{model}'\")),
}))
" 2>/dev/null)"

  if [ -z "$RESULT" ]; then
    printf "ERR\n"; continue
  fi
  "$PY" -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(f\"quant={d.get('quant','?')} swap={d.get('swap_blocks','?')} blocked={d.get('blocked',False)}\")
except Exception:
    print(\"parse-err\")
" <<<"$RESULT" 2>/dev/null || printf "ERR\n"
done

step "DONE."
exit 0