#!/usr/bin/env bash
# validate-marketplace.sh — schema check on .claude-plugin/marketplace.json
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MARKET="${ROOT}/.claude-plugin/marketplace.json"
PLUGIN="${ROOT}/.claude-plugin/plugin.json"

[ -f "$MARKET" ] || { echo "[FAIL] missing $MARKET"; exit 2; }
[ -f "$PLUGIN" ] || { echo "[FAIL] missing $PLUGIN"; exit 2; }

# Pick a working Python. Avoid Windows Microsoft-Store python3 stub
# that exits 49 with no execution. Prefer `python` (if present), then
# `python3.11`, then fall back to `python3`.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    if command -v python >/dev/null 2>&1; then PY=python
    elif command -v python3.11 >/dev/null 2>&1; then PY=python3.11
    elif command -v python3 >/dev/null 2>&1; then PY=python3
    else PY=python
    fi
fi
command -v "$PY" >/dev/null 2>&1 || { echo "[FAIL] python required"; exit 2; }

"$PY" - "$MARKET" "$PLUGIN" << 'PYEOF'
import json, re, sys
MARKET, PLUGIN = sys.argv[1], sys.argv[2]
market = json.load(open(MARKET))
plugin = json.load(open(PLUGIN))
errs = []
def slug(s): return bool(re.fullmatch(r"[A-Za-z0-9._-]{1,64}", s))
if not slug(market.get("name","")): errs.append("marketplace.name invalid")
plugins = market.get("plugins")
if not isinstance(plugins, list) or not plugins: errs.append("plugins must be non-empty list")
for i, p in enumerate(plugins or []):
    if not slug(p.get("name","")): errs.append(f"plugins[{i}].name invalid")
    src = p.get("source", {})
    if src.get("source") != "github": errs.append(f"plugins[{i}].source.source must be github")
    if not re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", src.get("repo","")): errs.append(f"plugins[{i}].source.repo invalid")
    if not p.get("description"): errs.append(f"plugins[{i}].description missing")
    v = str(p.get("version",""))
    if not re.fullmatch(r"\d+\.\d+\.\d+([+-][A-Za-z0-9._-]+)?", v): errs.append(f"plugins[{i}].version not semver")
if plugin.get("name") not in [p.get("name") for p in (plugins or [])]:
    errs.append(f"plugin name not in marketplace.plugins")
if errs:
    print("[FAIL] validate-marketplace")
    for e in errs: print(f"  - {e}")
    sys.exit(3)
print("[validate-marketplace] all checks passed")
PYEOF
