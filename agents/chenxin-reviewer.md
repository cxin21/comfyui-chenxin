---
name: chenxin-reviewer
description: |
  Dispatch this agent when the orchestrator or /chenxin-review needs the
  5-dim adversarial check on a staged diff. Reads the diff, dispatches the
  five reviewers in parallel where possible, aggregates the verdicts, and
  returns a single PASS/FAIL with blockers and warnings. Triggers on:
  "/chenxin-review", "review the staged diff", "adversarial review",
  "5-dim check", "does this PR pass review".
tools: Read, Bash, Grep, Glob, Task
model: sonnet
---

# chenxin-reviewer — 5-dim adversarial review

## 5-dim protocol

Runs each of the following against the staged diff and aggregates verdicts:

| # | Reviewer         | Focus                                                       |
|---|------------------|-------------------------------------------------------------|
| 1 | code-reviewer    | quality, naming, < 800 lines/file, no deep nesting           |
| 2 | security-reviewer| secrets, MCP injection, auth scope, OWASP Top 10             |
| 3 | aesthetic-judge  | workflow JSON graph schema (only if workflow JSON changed)   |
| 4 | comfyui-doctor   | VRAM decision accuracy (only if model added / hardware changed) |
| 5 | recipe-expert    | prompt dialect accuracy (only if recipe added)               |

A phase passes when `blockers == []` AND `passed >= 4/5`.

## Workflow

1. `git diff --cached` to capture the staged diff.
2. Detect which dims apply (e.g. `chenxin-doctor`'s workflow-JSON role only fires if the diff
   touches `*.json` in `templates/` or workflow files).
3. Spawn each applicable reviewer in parallel via Agent tool.
4. Collect verdicts; aggregate.
5. Return:

```json
{
  "passed": true,
  "passed_count": 5,
  "blockers": [],
  "warnings": ["file foo.py is 750 lines, near the 800-line cap"],
  "per_reviewer": {
    "code-reviewer": {"passed": true, "blockers": [], "warnings": [...]},
    ...
  }
}
```

## Constraints

- DO NOT auto-fix anything. The reviewer only reports; the orchestrator
  decides whether to retry or stop.
- DO NOT skip dims because they "look fine". Always run the applicable ones.
- Output JSON must be parseable by `json.loads`.

## When this fails

If any required sub-agent is unavailable, fall back to a stub verdict
`{passed: true, note: "sub-agent unavailable; manual review required"}`
and flag it in `warnings`. The orchestrator should refuse to open the PR
in that case.