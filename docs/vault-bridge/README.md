# Vault → Git Bridge / 反向同步桥

> **EN**: This directory mirrors critical vault decision notes into git-trackable files, so that PR reviewers + contributors can audit decisions via `git grep` + `git log` without needing Obsidian access. The "canonical" authoritative copy remains in the user's vault at `D:\ObsidianWorkSpace\workspace\` (per their global rule `~/.claude/rules/obsidian-workflow.md`).
>
> **中文**:此目录将关键 vault 决策笔记镜像到 git 可追踪的文件中,这样 PR 审查员 + 贡献者可以通过 `git grep` + `git log` 审计决策,无需 Obsidian 访问。Vault 中的"权威"主拷贝仍在 `D:\ObsidianWorkSpace\workspace\` 用户全局规则 `~/.claude/rules/obsidian-workflow.md`。

---

## Direction / 同步方向

```
plugin (writes) ──→ vault           ←──── bidirectional bridge ────→ git repo

hooks/scripts/on-write-sync-vault.sh  ──→  scripts/obsidian-sync.sh   ──writes→  $OBSIDIAN_VAULT_PATH/00-Inbox/processed/decision-<DATE>-<EVENT>.md
                                                                       
scripts/obsidian-sync.sh        ────────
  read by humans in vault                mirrored here (bi-weekly)        + future: bidirectional sync
```

The plugin always writes plugin → vault (via the `Write|Edit` hook).
This `docs/vault-bridge/` directory is the **reverse mirror**: humans can push key vault notes here on PR review, so the git history becomes self-contained.

---

## Mirrored Notes (this session, 2026-07-30)

Mirror-on-PR policy: any vault decision note ≥ 200 lines that drives plugin architecture gets copied here under the same filename.

| Vault source | Plugin path | When mirrored | Why |
|---|---|---|---|
| `20-Areas/comfyui-chenxin/design-2026-07-30.md` | [`20-Areas/comfyui-chenxin/design-2026-07-30.md`](../20-Areas/comfyui-chenxin/design-2026-07-30.md) (linked into vault-bridge by reference) | Originally mirrored | Vault IS the architectural canon — 8-layer L1-L8 design. |
| `00-Inbox/processed/decision-2026-07-30-comfyui-chenxin-p0.1.md` | `decision-p0.1.md` (this dir) | When P0.1 merged `5d574cb` | Phase 1 decision snapshot. |
| `00-Inbox/processed/decision-2026-07-30-comfyui-chenxin-p0.2.md` | `decision-p0.2.md` (this dir) | When P0.2 merged `8715150` | Phase 2 decision snapshot. |
| `00-Inbox/processed/decision-2026-07-30-comfyui-chenxin-p0.3.md` | `decision-p0.3.md` (this dir) | When P0.3 merged `154b1b6` | Phase 3 decision snapshot. |
| `00-Inbox/processed/decision-2026-07-30-comfyui-chenxin-v1-close.md` | [`decision-v1-close.md`](decision-v1-close.md) | When v1 closed `ba25e17` + `531dd62` | 8-phase v1 closure note — full inventory + acceptance. |
| `00-Inbox/processed/decision-2026-07-30-comfyui-chenxin-session-snapshot.md` | `decision-session-snapshot.md` (this dir) | Before user pause on session | Resume-from-pause context. |

---

## Usage / 使用方法

### Search vault-bridge in git

```bash
# Find any 5-dim review decision that referenced a specific skill
git grep -l "aesthetic-judge" docs/vault-bridge/

# List commit history that touched vault-bridge
git log --oneline docs/vault-bridge/

# View a single mirrored note
cat docs/vault-bridge/decision-v1-close.md
```

### Add new mirroring (PR pattern)

1. Write the decision to vault first per your workflow rules.
2. Copy the file to `docs/vault-bridge/` with the same filename (`.md`).
3. Update the "Mirrored Notes" table above + commit + PR.

### When NOT to mirror

- **Decision < 50 lines** — leave in vault, reference from PR description instead.
- **Personal scratchpad** — vault only.
- **Ephemeral session-only notes** — vault only.

---

## Future: full bidirectional sync

The plugin's `scripts/obsidian-sync.sh` is one-directional (plugin → vault).
A future Phase 3+ feature: `scripts/vault-mirror.sh` that runs on plugin-side schedule, hashes vault notes, and PRs divergent ones. Tracked as YAGNI; not implemented.
