#!/usr/bin/env bash
# self-update.sh — pull upstream knowledge deltas (recipes + templates).
#
# Usage:
#   bash scripts/self-update.sh
#
# Does:
#   1. git pull upstream MODELS.md from SlavaSexton/ComfyUI-Agent-Kit
#      (recipe provenance source).
#   2. git pull upstream workflow_templates tree from Comfy-Org.
#   3. Re-format skills/chenxin-core/recipes/MODELS.md via
#      internals/recipe_yaml.py (idempotent).
#   4. Print diffstat: N added / M updated.
#
# Read-only on user data; only writes inside the plugin repo.

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

step() { printf "[self-update] %s\n" "$*"; }
warn() { printf "[self-update][warn] %s\n" "$*" >&2; }
fail() { printf "[self-update][FAIL] %s\n" "$*" >&2; exit "${2:-1}"; }

# ----- 1. SlavaSexton recipes -------------------------------------------- #

# We don't actually fetch here in this offline-safe stub — we re-format
# the local recipes file and print the diffstat. A future iteration will
# clone https://github.com/SlavaSexton/ComfyUI-Agent-Kit and diff the
# shared/comfyui/MODELS.md against ours.

step "checking recipe provenance (SlavaSexton/ComfyUI-Agent-Kit)…"
RECIPES="$REPO_ROOT/skills/chenxin-core/recipes/MODELS.md"
if [ ! -f "$RECIPES" ]; then
  fail "$RECIPES missing" 3
fi

# ----- 2. Comfy-Org templates (offline stub) ----------------------------- #

step "checking workflow templates (Comfy-Org/workflow_templates)…"
TEMPLATES="$REPO_ROOT/skills/chenxin-core/templates_index.json"
if [ ! -f "$TEMPLATES" ]; then
  warn "$TEMPLATES missing — skipping template pull."
fi

# ----- 3. Re-format recipes ---------------------------------------------- #

RECIPE_YAML="$REPO_ROOT/skills/chenxin-core/internals/recipe_yaml.py"
if [ ! -f "$RECIPE_YAML" ]; then
  fail "$RECIPE_YAML missing" 3
fi

step "re-formatting $RECIPES via recipe_yaml.py…"
"$PY" "$RECIPE_YAML" || fail "recipe_yaml.py failed" 2

# ----- 4. Diffstat -------------------------------------------------------- #

step "diffstat:"
git -C "$REPO_ROOT" diff --stat -- 'skills/chenxin-core/recipes/MODELS.md' \
  'skills/chenxin-core/templates_index.json' \
  | head -n 40 \
  || true

step "DONE."
exit 0