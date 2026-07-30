#!/usr/bin/env bash
# test_smoke.sh — P0.3 smoke test for chenxin-core internals + scripts.
#
# Targets the chenxin-core internals (recipe_yaml, recipe_lookup,
# hardware_decide) and the new scripts. Does NOT touch the already-merged
# P0.2 MCP CLIs — those have their own test at mcp/extensions/test_smoke.sh.
#
# Exit codes:
#   0   all pass
#   non-zero   first failing tool's exit code

set -u

cd "$(dirname "$0")/.."  # repo root

FAIL=0
PASS=0

PY=python
[ -n "${PYTHON:-}" ] && PY="$PYTHON"

echo "[smoke] P0.3 chenxin-core internals + scripts sanity test"
echo "[smoke] cwd: $(pwd)"
echo "[smoke] python: $($PY --version 2>&1)"

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

probe_json() {
  local name="$1"; shift
  local out
  out="$("$@" 2>/dev/null)"
  local code=$?
  if [ "$code" -eq 0 ] && printf '%s' "$out" | "$PY" -c "import sys,json; json.loads(sys.stdin.read())" >/dev/null 2>&1; then
    printf "  [pass] %s\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "  [FAIL] %s (exit=%d, json-parse failed)\noutput: %s\n" "$name" "$code" "$out"
    FAIL=$((FAIL + 1))
  fi
}

assert_file() {
  local name="$1"
  local path="$2"
  if [ -f "$path" ]; then
    printf "  [pass] %s exists\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "  [FAIL] %s missing at %s\n" "$name" "$path"
    FAIL=$((FAIL + 1))
  fi
}

assert_frontmatter() {
  local name="$1"
  local path="$2"
  if [ ! -f "$path" ]; then
    printf "  [FAIL] %s missing at %s\n" "$name" "$path"
    FAIL=$((FAIL + 1))
    return
  fi
  # Frontmatter must be a YAML block delimited by `---` lines.
  if head -n 1 "$path" | grep -qE '^---$' && sed -n '2,200p' "$path" | grep -qE '^---$'; then
    printf "  [pass] %s has frontmatter\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "  [FAIL] %s missing frontmatter delimiters\n" "$name"
    FAIL=$((FAIL + 1))
  fi
}

echo
echo "[smoke] 1) chenxin-core internals --help + idempotent round-trip"
run "recipe_yaml --help"     "$PY" skills/chenxin-core/internals/recipe_yaml.py --help
run "recipe_lookup --help"   "$PY" skills/chenxin-core/internals/recipe_lookup.py --help
run "hardware_decide --help" "$PY" skills/chenxin-core/internals/hardware_decide.py --help
run_bogus "recipe_yaml bogus flag"     "$PY" skills/chenxin-core/internals/recipe_yaml.py --bogus
run_bogus "recipe_lookup no --model"   "$PY" skills/chenxin-core/internals/recipe_lookup.py
run_bogus "hardware_decide no --model" "$PY" skills/chenxin-core/internals/hardware_decide.py --vram 8

echo
echo "[smoke] 2) recipe_yaml round-trip (--check must report up-to-date)"
run "recipe_yaml --check"    "$PY" skills/chenxin-core/internals/recipe_yaml.py --check
run "recipe_yaml --check again" "$PY" skills/chenxin-core/internals/recipe_yaml.py --check

echo
echo "[smoke] 3) recipe_lookup returns valid JSON for known model"
probe_json "recipe_lookup --model flux_1 --n 5" \
  "$PY" skills/chenxin-core/internals/recipe_lookup.py --model flux_1 --n 5
probe_json "recipe_lookup --model wan (substring)" \
  "$PY" skills/chenxin-core/internals/recipe_lookup.py --model wan --n 3

echo
echo "[smoke] 4) hardware_decide returns valid JSON for known model"
probe_json "hardware_decide --vram 8 --model anima" \
  "$PY" skills/chenxin-core/internals/hardware_decide.py --vram 8 --model anima

echo
echo "[smoke] 5) all new commands / agents / hooks files exist + parse"
for f in \
  commands/chenxin-init.md \
  commands/chenxin-build.md \
  commands/chenxin-review.md \
  commands/chenxin-doctor.md \
  commands/chenxin-publish.md \
  commands/chenxin-update.md \
  agents/chenxin-orchestrator.md \
  agents/chenxin-builder.md \
  agents/chenxin-reviewer.md \
  agents/chenxin-doctor.md \
  agents/chenxin-update-bot.md \
  agents/chenxin-publisher.md \
  skills/chenxin-core/SKILL.md \
  skills/chenxin-core/internals/context_graph.md \
  hooks/hooks.json
do
  assert_file "$(basename "$f")" "$f"
  case "$f" in
    # Claude Code only auto-loads files with frontmatter; internal docs
    # under internals/ are read-on-demand and don't need it.
    *.md)
      case "$f" in
        */internals/*) ;;
        *) assert_frontmatter "$(basename "$f")" "$f" ;;
      esac
      ;;
  esac
done

echo
echo "[smoke] 6) scripts/ + hooks/scripts/ files exist + are syntactically sane"
for f in \
  scripts/install.sh \
  scripts/install.ps1 \
  scripts/bootstrap.sh \
  scripts/phase-next.sh \
  scripts/find-next-phase.sh \
  scripts/obsidian-sync.sh \
  scripts/self-update.sh \
  scripts/validate-plugin-schema.sh \
  hooks/scripts/on-session-start.sh \
  hooks/scripts/on-write-sync-vault.sh \
  hooks/scripts/on-stop-phase-gate.sh
do
  assert_file "$(basename "$f")" "$f"
  if [[ "$f" == *.sh ]]; then
    if bash -n "$f" 2>/dev/null; then
      printf "  [pass] %s bash -n\n" "$(basename "$f")"
      PASS=$((PASS + 1))
    else
      printf "  [FAIL] %s bash -n failed\n" "$(basename "$f")"
      FAIL=$((FAIL + 1))
    fi
  fi
done

echo
echo "[smoke] 7) phase-next / find-next-phase / obsidian-sync / validate-plugin-schema"
run "phase-next.sh"        bash scripts/phase-next.sh
run "find-next-phase.sh"   bash scripts/find-next-phase.sh

# obsidian-sync may fail to write the vault (vault missing), but must exit 0.
run "obsidian-sync.sh smoke"  bash scripts/obsidian-sync.sh smoke-$$ || true

# validate-plugin-schema: requires plugin.json + marketplace.json + the new dirs.
run "validate-plugin-schema.sh"  bash scripts/validate-plugin-schema.sh

echo
echo "[smoke] summary: pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]