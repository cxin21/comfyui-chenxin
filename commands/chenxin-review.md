---
description: Manually trigger the 5-dim adversarial review on the staged diff.
argument-hint: "[--strict]  (optional; --strict lowers pass threshold to all 5/5)"
---

# /chenxin-review

Dispatches `chenxin-reviewer` against the staged git diff.

```bash
git add -A                       # stage the changes
/chenxin-review                  # review what's staged
/chenxin-review --strict         # require all 5/5 reviewers (default: 4/5)
```

The reviewer runs the 5-dim adversarial protocol from `ROADMAP.md`:

1. **code-reviewer**      — quality, naming, < 800 lines/file
2. **security-reviewer**  — secrets, MCP injection, auth scope
3. **aesthetic-judge**    — workflow JSON graph schema (if applicable)
4. **comfyui-doctor**     — VRAM decision accuracy (if model added)
5. **recipe-expert**      — prompt dialect accuracy (if recipe added)

Each reviewer returns `{passed: bool, blockers: [...], warnings: [...]}`.
A phase passes when `blockers == []` AND `passed >= 4/5`.

## Output shape

```
[review] 1/5 code-reviewer      … PASS (0 blockers, 1 warning)
[review] 2/5 security-reviewer  … PASS (0 blockers, 0 warnings)
[review] 3/5 aesthetic-judge    … SKIP (no workflow JSON in diff)
[review] 4/5 comfyui-doctor     … PASS
[review] 5/5 recipe-expert      … FAIL (1 blocker: dialect wrong for Hunyuan)
[review] summary: passed=4/5, blockers=1
```

## When this is blocked

If `agents/chenxin-reviewer.md` is missing or the user lacks the required
sub-agents, `/chenxin-review` prints an actionable error pointing at
`scripts/phase-next.sh` as the fallback.