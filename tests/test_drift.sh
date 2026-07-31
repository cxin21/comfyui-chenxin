#!/usr/bin/env bash
# test_drift.sh — Tier-1 cross-document drift detection.
#
# Asserts that facts duplicated across multiple plugin docs are
# CONSISTENT — no drift. Every assertion exercises a real file
# (no mocks).
#
# Catches: workflow node-ID drift, 5-dim reviewer-name drift,
# MCP namespace drift, marketplace URL drift, install URL drift.
#
# Exit: 0 = all consistent, 1 = drift found.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pass() { printf '  [pass] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
FAILS=0

echo "=== Group 1 — Anima workflow node white-list consistency ==="
# These 3 docs must all show {3, 4} as the AnimaStandardV7 white-list.
# Accept both bolded (**3**) and plain (| 3 |) table forms.
for src in skills/chenxin-core/internals/workflow-config-guard.md \
          skills/chenxin-core/internals/workflow-resolver.md \
          skills/manga-stage-2-panels/SKILL.md; do
    if grep -qE "\b3\b.*(?:ImpactWildcardProcessor|POSITIVE|positive.*prompt)" "$src" 2>/dev/null \
       && grep -qE "\b4\b.*(?:ImpactWildcardProcessor|NEGATIVE|negative.*prompt)" "$src" 2>/dev/null; then
        pass "$src mentions nodes 3+4 for Anima"
    else
        fail "$src missing Anima nodes 3+4 white-list"
    fi
done

echo
echo "=== Group 2 — ltx23 workflow node white-list consistency ==="
# Each of {121, 593, 149, 1792, 1793} must appear at least once in each
# of these docs (order-free, can be on different lines / columns).
for src in skills/chenxin-core/internals/workflow-config-guard.md \
          skills/chenxin-core/internals/workflow-resolver.md \
          skills/manga-stage-4-motion/SKILL.md \
          agents/comfyui-director.md; do
    missing=""
    for n in 121 593 149 1792 1793; do
        if ! grep -qE "\b$n\b" "$src" 2>/dev/null; then
            missing="$missing $n"
        fi
    done
    if [ -z "$missing" ]; then
        pass "$src mentions all 5 ltx23 white-list nodes"
    else
        fail "$src missing ltx23 nodes:$missing"
    fi
done

echo
echo "=== Group 3 — 5-dim reviewer slot 3 is NOT aesthetic-judge (Explore §7.7 fix) ==="
# Across chenxin-reviewer.md, SKILL.md, ROADMAP.md. Active 5-dim
# lists must not use the deleted 'aesthetic-judge' as slot 3.
for src in agents/chenxin-reviewer.md skills/chenxin-core/SKILL.md ROADMAP.md; do
    if grep -E '\| 3 .+[aA]esthetic-judge' "$src" >/dev/null 2>&1; then
        fail "$src still references 'aesthetic-judge' as 5-dim slot 3"
    else
        pass "$src has chenxin-doctor (or different label) as 5-dim slot 3"
    fi
done

echo
echo "=== Group 4 — MCP namespace is mcp__comfyui-mcp__ (NOT mcp__comfyui-mcp-server) ==="
# Active instructions only. The version-history mention in
# agents/comfyui-director.md line ~304 + application-inventory.md
# migration notes are intentionally allowed.
matches=$(grep -rln 'mcp__comfyui-mcp-server' --include="*.md" --include="*.py" --include="*.sh" . 2>/dev/null \
    | grep -v "\.git" \
    | grep -v "agents/comfyui-director.md" \
    | grep -v "application-inventory.md" \
    | grep -v "tests/test_drift.sh" || true)
if [ -z "$matches" ]; then
    pass "no wrong-namespace refs in active instructions"
else
    fail "wrong-namespace refs: $matches"
fi

echo
echo "=== Group 5 — marketplace URL is cxin21/comfyui-chenxin (no 'chenxin' placeholder) ==="
for f in .claude-plugin/marketplace.json .claude-plugin/plugin.json scripts/install.sh scripts/install.ps1; do
    if grep -q "chenxin/comfyui-chenxin" "$f" 2>/dev/null; then
        fail "$f still contains placeholder 'chenxin/comfyui-chenxin'"
    else
        pass "$f uses cxin21/comfyui-chenxin"
    fi
done

echo
echo "=== Group 6 — 'Differences from SlavaSexton' section is removed ==="
for f in README.md README.en.md; do
    if [ -f "$f" ] && grep -q "Differences from SlavaSexton" "$f"; then
        fail "$f still has 'Differences from SlavaSexton' section"
    else
        pass "$f clean of comparison-to-SlavaSexton section"
    fi
done

echo
echo "=== Group 7 — recipe count in MODELS.md is >= 70 ==="
actual=$(grep -c '^id: ' skills/chenxin-core/recipes/MODELS.md 2>/dev/null || echo 0)
if [ "$actual" -ge 70 ]; then
    pass "MODELS.md has $actual recipe blocks (>= 70)"
else
    fail "MODELS.md has only $actual recipe blocks (< 70)"
fi

echo
echo "=== Group 8 — templates_index.json count >= 500 ==="
# The file is {"templates": [...], "totals": {...}, ...}. The
# canonical count is the `templates` array length.
n_templates=$(grep -c '^\s*{' skills/chenxin-core/templates_index.json 2>/dev/null || echo 0)
# A more reliable count: number of "id": "..." entries (one per template).
n_ids=$(grep -cE '^\s*"id":' skills/chenxin-core/templates_index.json 2>/dev/null || echo 0)
if [ "$n_ids" -ge 500 ]; then
    pass "templates_index.json has $n_ids template id entries (>= 500)"
else
    fail "templates_index.json has only $n_ids template id entries (< 500)"
fi

echo
echo "=== Group 9 — 6 commands each have description: in frontmatter ==="
for cmd in commands/chenxin-*.md; do
    if grep -q "^description:" "$cmd"; then
        pass "$(basename $cmd) has frontmatter description"
    else
        fail "$(basename $cmd) missing frontmatter description"
    fi
done

echo
echo "=== Group 10 — no 'aesthetic-judge skill' active invocation in skills/agents/commands ==="
matches=$(grep -rE "aesthetic-judge skill" --include="*.md" . 2>/dev/null | grep -v "\.git" | grep -vE "(DO NOT|已 absorbed|absorbed into|absorbed aesthetic-judge|已 absorbed|absorbed skill|absorbed to|absorbed into skill|absorbed by)" || true)
if [ -z "$matches" ]; then
    pass "no active 'aesthetic-judge skill' invocations"
else
    fail "active 'aesthetic-judge skill' invocations found:"
    echo "$matches" | sed 's/^/    /'
fi

echo
if [ "$FAILS" -eq 0 ]; then
    echo "[drift] all consistency checks passed"
    exit 0
else
    echo "[drift] $FAILS inconsistency(ies) found"
    exit 1
fi
