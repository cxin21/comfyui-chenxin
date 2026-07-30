---
name: chenxin-update-bot
description: |
  Dispatch this agent for /chenxin-update. Runs `scripts/check_updates.py`
  to diff local L3 substrate (recipes + templates + skills + RSS) against
  four upstream sources, then opens a PR per surface so each diff is
  independently reviewable. Cheap (Haiku) — designed to run weekly.
  Triggers on: "/chenxin-update", "pull knowledge deltas", "sync recipes",
  "weekly update", "self-update".
tools: Read, Bash, Grep, Glob
model: haiku
---

# chenxin-update-bot — weekly knowledge pull

## Workflow

### 1. Decide mode

- Default: `python3 scripts/check_updates.py --dry-run` (read-only).
- Apply: `python3 scripts/check_updates.py --apply` (creates a
  `phase/P1.2-self-update-<YYYY-MM-DD>` branch with a report commit).
- Apply is the cron-mode path; the GitHub Actions workflow
  (`.github/workflows/weekly-update.yml`) calls it on Mondays 09:00 UTC.

### 2. Inspect the JSON envelope

The daemon emits a machine-readable JSON object on stdout:

```json
{
  "schema_version": 1,
  "checked_at_utc": "2026-07-30T12:00:00Z",
  "mode": "dry-run" | "apply",
  "sources": {
    "slavasexton_recipes":   { "status": "drift"|"up-to-date"|"fetch_failed", "diff": {...} },
    "comfy_org_templates":   { "status": "drift"|"up-to-date"|"fetch_failed", "diff": {...} },
    "comfy_org_skills":      { "status": "up-to-date"|"fetch_failed",        "diff": {...} },
    "hf_blog_rss":           { "status": "ok"|"fetch_failed",                "items": [...]  }
  },
  "recommended_action": "open PR" | "up-to-date" | "manual review"
}
```

For each source, the `status` field drives the next step.

### 3. Branch + PR per surface

- `slavasexton_recipes.status == "drift"`
  → branch `auto/knowledge-update/recipes-<date>` from `main`
  → `git checkout -b auto/knowledge-update/recipes-<date>`
  → copy upstream MODELS.md into `skills/chenxin-core/recipes/MODELS.md`
  → run `python3 scripts/diff_recipes.py --json OLD NEW` to surface
     the structural diff (added / removed / changed) for the PR body
  → commit + open PR with label `auto/knowledge-update/recipes`.
- `comfy_org_templates.status == "drift"`
  → branch `auto/knowledge-update/templates-<date>` from `main`
  → re-run the P0.1 templates fetch (see `bootstrap.sh`) to refresh
     `skills/chenxin-core/templates_index.json`
  → open PR with label `auto/knowledge-update/templates`.
- `comfy_org_skills.status == "fetch_failed"` (rare; log-only)
  → file an issue tagged `auto/knowledge-update/skills` with the
     captured error; do NOT attempt a force-fix.
- `hf_blog_rss.items` — surface in PR body; do not auto-edit substrate.

### 4. PR body

Always include the dry-run JSON (as a fenced block) plus a per-surface
table:

```
[update-bot] recipes added: +5
[update-bot] recipes updated: 3
[update-bot] recipes removed: -1 (deprecated upstream)
[update-bot] templates added: +12
[update-bot] templates updated: 7
[update-bot] PR: https://github.com/chenxin/comfyui-chenxin/pull/<n>
```

### 5. Constraints

- Read-only on the user's local ComfyUI install (never edits workflows or models).
- Idempotent — running twice in the same week is a no-op (the diff still
  re-evaluates but the PR gets recreated only on net-new drift).
- NEVER pushes to remote without the user explicitly invoking `/chenxin-update`.
- If `git checkout -b` or `git fetch` fails, abort and print a human-action
  message; do not force-resolve.
- If two surfaces drift in the same run, open TWO separate PRs (one per
  surface) — do not bundle. Each surface is independently reviewable.
