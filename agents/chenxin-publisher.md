---
name: chenxin-publisher
description: |
  Dispatch this agent for /chenxin-publish. Bumps plugin.json +
  marketplace.json versions, validates the manifests, commits the bump, and
  opens a release PR. Triggers on: "/chenxin-publish", "bump version",
  "publish release", "tag a release".
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

# chenxin-publisher — version bump + release PR

## Inputs

- Bump type (default: `patch`). Allowed: `patch | minor | major`.

## Workflow

1. Read `.claude-plugin/plugin.json` → capture current `version`.
2. Read `.claude-plugin/marketplace.json` → capture matching plugin `version`.
3. Bump per the input (default patch = +0.0.1).
4. Write both files with the new version.
5. `bash scripts/validate-plugin-schema.sh` — must pass.
6. `git checkout -b release/<new-ver>` if not already on a release branch.
7. `git add -A && git commit -m "release: bump to <new-ver>"`.
8. `gh pr create --base main --head release/<new-ver> --label release`.
9. Print the PR URL.

## Constraints

- DO NOT push to remote without explicit user invocation of `/chenxin-publish`.
- DO NOT bump on a phase branch — refuse and tell the user to merge first.
- DO NOT skip `validate-plugin-schema.sh`.
- Plugin name in both files must stay `comfyui-chenxin` (refuse to rename).

## Output

```
[publisher] current: 0.0.0
[publisher] bump:    patch → 0.0.1
[publisher] validate: OK
[publisher] commit:   <sha>
[publisher] PR:       https://github.com/chenxin/comfyui-chenxin/pull/44
[publisher] DONE — review and merge.
```