"""Pre-compile quality gate.

Encodes rules from:
- references/quality/conflict-table.md (5 hard-conflict categories)
- references/quality/tag-count-ruler.md (count percentiles + per-slot targets)
- references/quality/style-consistency.md (cross-slot worldview check)

Usage:
    from scripts.preflight import preflight_check
    result = preflight_check(segments, complexity)
    if not result['ok']:
        for e in result['errors']:
            print(f"ERROR: {e}")
"""
from __future__ import annotations


# Conflict pairs from conflict-table.md
VIEW_CONFLICTS = [
    {("pov",), ("full body", "cowboy shot")},
    {("from front",), ("from behind",)},
    {("looking at viewer",), ("facing away",)},
    {("from above",), ("from below",)},
]
IDENTITY_CONFLICTS = [
    {("solo",), ("hetero", "1boy", "yuri")},
    {("completely nude",), ("specific clothing",)},  # simplify: any clothing tag
    {("sleeping", "unconscious"), ("looking at viewer",)},
    {("blindfold",), ("heart-shaped pupils", "rolling eyes")},
]

# Tag-count thresholds from tag-count-ruler.md
COUNT_HARD_CAPS = {
    "simple": 40,
    "standard": 50,
    "complex": 70,
}


def _tag_set(segments: list[dict]) -> set[str]:
    return {seg.get("text", "").strip().lower() for seg in segments if seg.get("text")}


def _check_conflicts(tags: set[str]) -> list[str]:
    errors = []
    for pair_set in VIEW_CONFLICTS + IDENTITY_CONFLICTS:
        for group_a, group_b in [(list(s)[0], list(s)[1]) for s in pair_set]:
            a_hit = group_a in tags
            b_hit = any(t in tags for t in group_b)
            if a_hit and b_hit:
                errors.append(f"conflict: {group_a} + {group_b}")
    return errors


def _check_count(segments: list[dict], complexity: dict) -> list[str]:
    """Return warnings (not errors) if over the hard cap."""
    n = sum(1 for s in segments if s.get("text"))
    # Infer complexity tier from subjects count
    subjects = complexity.get("subjects", 1)
    if subjects >= 3:
        tier = "complex"
    elif subjects >= 2:
        tier = "standard"
    else:
        tier = "simple"
    cap = COUNT_HARD_CAPS[tier]
    if n > cap:
        return [f"tag count {n} > hard cap {cap} for {tier}"]
    return []


def _check_style(segments: list[dict]) -> list[str]:
    """Cross-slot worldview check (simplified)."""
    errors = []
    tags = _tag_set(segments)
    # Hanfu + cyberpunk city is a classic mismatch
    if any("hanfu" in t for t in tags) and any("cyberpunk city" in t for t in tags):
        errors.append("style: hanfu + cyberpunk city worldview mismatch")
    return errors


def preflight_check(segments: list[dict], complexity: dict) -> dict:
    """Run all pre-compile quality gates.

    Args:
        segments: list of {field, text, fact_ids} dicts (positive stream).
        complexity: dict with subjects, explicit_relations, etc.

    Returns:
        {ok: bool, errors: list[str], warnings: list[str]}
    """
    tags = _tag_set(segments)
    errors = _check_conflicts(tags) + _check_style(segments)
    warnings = _check_count(segments, complexity)
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }