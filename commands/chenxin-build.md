---
description: Execute the next unchecked phase from SPEC.md and open a PR.
argument-hint: "[phase-id]  (optional; default = first [- ] in SPEC.md)"
---

# /chenxin-build

Dispatches the `chenxin-orchestrator` agent against the current branch.

```bash
# Find the next unchecked phase:
bash scripts/find-next-phase.sh
```

If `phase-id` is supplied (e.g. `P0.4`), the orchestrator builds that one
explicitly; otherwise it reads `SPEC.md` and picks the first `^- [ ]` entry.

The orchestrator:

1. Spawns `chenxin-builder` for the phase scope (writes files, updates SPEC).
2. Spawns `chenxin-reviewer` against the staged diff (5-dim adversarial).
3. If review passes (`blockers == []` AND `passed >= 4/5`), opens a PR via
   `gh pr create` against `main`.
4. If review fails, prints the blocker list and stops. Re-run
   `/chenxin-build` after fixing.

## Exit semantics

| Result   | Meaning                                                       |
|----------|---------------------------------------------------------------|
| 0        | Phase built and PR opened                                     |
| 1        | Review blocker — fix and re-run                               |
| 2        | Usage error (bad phase-id, no SPEC.md, no git remote)         |
| 3        | Builder / reviewer agent failure (see logs)                   |

## Manual fallback

If `agent/chenxin-orchestrator` is unavailable (e.g. plugin not loaded),
run `bash scripts/phase-next.sh` for a dry-run that just prints the next
unchecked phase.