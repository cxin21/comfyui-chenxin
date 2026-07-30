---
description: Pull upstream L3 knowledge deltas (recipes, templates).
argument-hint: (no args)
---

# /chenxin-update

Dispatches the haiku-powered `chenxin-update-bot` agent. It runs weekly:

```bash
bash scripts/self-update.sh
```

This script:

1. `git pull` SlavaSexton/ComfyUI-Agent-Kit `shared/comfyui/MODELS.md`
   (source of recipe provenance).
2. `git pull` Comfy-Org/workflow_templates tree.
3. Re-formats `skills/chenxin-core/recipes/MODELS.md` via
   `internals/recipe_yaml.py` (idempotent — only writes if diff exists).
4. Prints a diffstat: N recipes added, M templates added, K recipes updated.

If the diff is non-empty, the bot stages the changes and opens a PR
labelled `auto/knowledge-update` with the diffstat in the body.

## Exit semantics

| Result | Meaning                                                       |
|--------|---------------------------------------------------------------|
| 0      | No upstream changes (or PR opened cleanly)                    |
| 1      | Network failure — retry next week                              |
| 2      | Conflict (local edits to MODELS.md) — human review required    |
| 3      | recipe_yaml.py error — file is now malformed; escalate        |

## Manual fallback

```bash
bash scripts/self-update.sh          # full update
python skills/chenxin-core/internals/recipe_yaml.py --check   # verify idempotency
```