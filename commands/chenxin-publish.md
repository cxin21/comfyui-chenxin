---
description: Bump plugin + marketplace version and open a release PR.
argument-hint: "[patch|minor|major]  (default = patch)"
---

# /chenxin-publish

Dispatches `chenxin-publisher` agent. It:

1. Reads current version from `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json`.
2. Bumps per `[patch|minor|major]` (default patch: +0.0.1).
3. Validates the new manifest against `scripts/validate-plugin-schema.sh`.
4. Commits the version bump.
5. Opens a release PR (`gh pr create --base main --head release/<new-ver>`).
6. Prints the PR URL for the user to review.

## Required secrets / config

- `gh` CLI authenticated (the publisher reuses the user's existing token).
- Both manifest files present and parseable as JSON.
- The current branch must be `main` (or `release/<x>`) — publisher refuses
  to bump from a phase branch to avoid double-versioning.

## Output shape

```
[publisher] current version: 0.0.0
[publisher] bump: patch
[publisher] new version: 0.0.1
[publisher] validating manifests… OK
[publisher] committing bump…
[publisher] opening PR… https://github.com/chenxin/comfyui-chenxin/pull/42
[publisher] DONE — review and merge.
```

## When this fails

- If `gh` is not authenticated, print `gh auth login` instructions.
- If the branch already has a release PR, print that PR and stop.
- If `validate-plugin-schema.sh` fails, print the offending field and stop.