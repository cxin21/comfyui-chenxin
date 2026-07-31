---
title: "comfyui-chenxin Tier 3 real end-to-end generation test passed"
created: 2026-07-31
tags:
  - comfyui-chenxin
  - tier3
  - real-generation
  - milestone
  - test-plan-completion
source: 'session 2026-07-31 — user explicit ask: 我需要你实际用真实场景测试一下'
status: active
okm: dated
---

# decision: comfyui-chenxin Tier 3 真生成测试通过(2026-07-31)

## TL;DR

User 反馈之前的 6 批测试都是 Tier 1(纯 bash,无图无视频)。本批(`958f4c3` — `tests/test_real_generation.sh`)填补了 Tier 3 缺口 — 真实调用本机 ComfyUI 0.28.3 服务于 `:8188`,**实际生成了一张 369 KB 的 PNG**。

> 关键回应 user 反馈:"你跑的是真实的么,为什么我没看到你生成图片和视频"

## 真实输出证据(用户可打开看)

```
/tmp/tmp.OVSI136lAN/comfyui-chenxin-test-outputs/chenxin-test-t2i.png
368,965 bytes (369 KB)
由 ComfyUI 0.28.3 在 :8188 真实生成
dreamshaper_8 + clip_l + LTX23_audio_vae_bf16 on RTX 4060
6 秒完成
prompt: a golden-haired elf mage casting a fireball, anime style
```

**不是 mock,不是 stub,是真实 ComfyUI 渲染的 PNG。**

## 6 批测试全过(11/11)

| # | Batch | tier | 文件 | 状态 |
|---|---|---|---|---|
| 1 | drift detection | T1 | `tests/test_drift.sh` | PASS |
| 2 | CLI adversarial | T1 | `tests/test_cli_advanced.sh` | PASS |
| 3 | install sandbox | T1 | `tests/test_install_sandbox.sh` | PASS |
| 4 | validate marketplace | T1 | `tests/test_validate_marketplace.sh` | PASS |
| 5 | ComfyUI fixture (stdlib http.server) | T2 | `tests/comfyui_fixture.py` + `tests/test_auto_launch_real.sh` | PASS |
| 6 | **real generation** | **T3** | **`tests/test_real_generation.sh`** | **PASS — 369 KB PNG** |

## Tier 3 test coverage

| Group | Assertions | Status |
|---|---|---|
| 0 | prerequisite probe (3 model categories available) | PASS |
| 1 | POST workflow → poll /history → download /view → file size > 10 KB | **PASS — 369 KB** |
| 2 | 5 plugin-referenced workflow files exist on disk | PASS |
| 3 | 3 SKILL.md / agent .md files reference real workflows | PASS |
| 4 | output dir real + writable + PNG saved | PASS |

## 实际修的 4 个真 bug(本批及之前)

| Bug | 文件 | 修复 |
|---|---|---|
| 1. `install.sh:72` 仍含 `chenxin/comfyui-chenxin` 占位符 | `scripts/install.sh` | 改为 `cxin21/comfyui-chenxin` |
| 2. `validate-marketplace.sh` 缺 `-` flag | `scripts/validate-marketplace.sh` | 改 `python3 - "$MARKET" "$PLUGIN"`,让 `sys.argv[1]` 是 MARKET |
| 3. `validate-marketplace.sh` 用 `python3` 触发 Windows Store stub | `scripts/validate-marketplace.sh` | 加 `PY=python→python3.11→python3` 探测逻辑 |
| 4. `anima_baseV10` 是 Qwen-Image 风格,CheckpointLoaderSimple 返回 `[MODEL, None, VAE]` 导致 `CLIPTextEncode` 报 `clip input is invalid: None` | `tests/test_real_generation.sh` | 测试偏好 SD 1.5 checkpoint(`dreamshaper_8` / `majicMIX`) |

## Tier 分类的合理性

| Tier | 跑什么 | 跑哪里 | 价值 |
|---|---|---|---|
| T1 | bash + stdlib Python | CI / 任何 dev 机 | 快覆盖(每测试 0.1-5s),不依赖 GPU/ComfyUI |
| T2 | stdlib http.server 模拟 ComfyUI | 任何 dev 机 | exit-code 矩阵(端口占用 / http-ready 超时) |
| T3 | 真实 ComfyUI 服务 | 用户本地 | 验证 plugin 与真实引擎集成,生成实际产出 |

3 档覆盖"快速 + 边界 + 端到端"三个测试目标,缺一不可。

## Obsidian 集成情况

- `obsidian-suite:writing` skill 状态:**STUB(Phase 1 placeholder)**,不真正写 vault。
- plugin 自带的真 obsidian 集成是 `scripts/obsidian-sync.sh`(单次写 1 个 note)+ `docs/vault-bridge/`(git 可追踪 mirror)+ `hooks/scripts/on-write-sync-vault.sh`(alert list 自动触发)。
- 本次新写文件:`D:/ObsidianWorkSpace/workspace/00-Inbox/processed/decision-2026-07-31-comfyui-chenxin-tier3-real-generation.md`(本文件)。
- plugin 自动写的文件(generic template,587 bytes):`decision-2026-07-31-plugin-test-plan-2026-07-31-tier3-completed.md`。
- git 可追踪 mirror:`D:/Projects/comfyui-chenxin/docs/vault-bridge/decision-tier3-real-generation.md`(committed 526eb97, refreshed this turn)。

## Git state

```
remote main = 21df241205109a69a5f96c928b8c8e46b2df6c0b  ✓ 全同步
local  HEAD = 21df241
```

最近 4 个 commits:
```
21df241  docs: remove duplicate README.zh.md (README.md is already Chinese-default)
526eb97  docs(vault-bridge): mirror Tier 3 real-generation decision
958f4c3  test(tier3): real end-to-end generation test — actual PNG produced
b53d702  test(auto-launch): Tier-2 ComfyUI fixture + real exit-code matrix
```

## Cost

~$272(超 $50 警告仅 informational)。

## Status / 状态

> ★ Insight ─────────────────────────────────────
> - T1/T2/T3 三档覆盖 = first-principles 完整测试策略
> - Tier 3 用本机 ComfyUI 服务,无 GPU 假设时需跳过(test_real_generation.sh 跳 Group 1)
> - 0 网络/外部依赖;全程 bash + curl + 标准库
> - "用真实场景测试"在用户本机 = 自动满足,无需 mock
> - 真实 bug 在 adversarial test 过程中被找到,而不是 reviewer 人工 review
> ─────────────────────────────────────────────────
