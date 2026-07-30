# Obsidian Vault Sync Contract

This plugin **writes one file** to your Obsidian vault every time a sensitive file in the repo is touched. The contract is intentionally minimal — one file per event, never anything inside your `P-*` project notes.

## What the hook fires on

`hooks/scripts/on-write-sync-vault.sh` listens for any `Write|Edit` tool call whose target path contains:

- `SPEC.md`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

When matched, the hook calls `scripts/obsidian-sync.sh post-write-<sanitized-path>`.

## What `scripts/obsidian-sync.sh` writes

```
$OBSIDIAN_VAULT_PATH/00-Inbox/processed/decision-YYYY-MM-DD-<event>.md
```

Default vault: `D:/ObsidianWorkSpace/workspace/00-Inbox/processed/` (overridable via `OBSIDIAN_VAULT_PATH`).

Frontmatter injected:

```yaml
---
date: YYYY-MM-DD
branch: <git branch>
event: <sanitized event>
trigger: post-write hook (chenxin plugin)
---
```

## Safety properties

| Property | Mechanism |
|---|---|
| Whitelist-only EVENT | `EVENT_RAW=$(printf '%s' "$1" | tr -cd 'A-Za-z0-9._-')` |
| Defense-in-depth path check | `case "$DST" in "$INBOX"/*) ;;` else warn-and-skip |
| Missing vault is non-fatal | `if [ ! -d "$VAULT" ]; then exit 0; fi` |
| Idempotent within a day | Same `(TODAY, EVENT)` tuple overwrites same file |

## Smoke test

`tests/test_obsidian_sync.sh` covers the four safety properties in a sandboxed `/tmp` vault.

## Disabling

Set `OBSIDIAN_VAULT_PATH=/dev/null` to no-op the hook without removing it.
