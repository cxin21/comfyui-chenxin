---
name: manga-stage-2-panels
description: "AI 漫剧 Stage 2 — 分镜面板自动生成。锁定 AnimaStandardV7 工作流，仅修改 prompt + LoRA 配置，自动生成 PNG 面板。可选 IP-Adapter / ControlNet 增强（v2.0）。Also load prompt-forge first for VRAM/recipe context."
version: 2.1.0
author: Claude Code
status: legacy
triggers: []
allowed-tools: Bash, Read, Write, "mcp__comfyui-mcp__*"
---
> Legacy compatibility only. Do not route production work here; use
> skills/prompt-forge/SKILL.md and its four-stage character-to-video flow.

# Manga Stage 2 — 分镜面板生成 (v2.1, ported)

> **Plugin path**: `skills/manga-stage-2-panels/SKILL.md`
> **Upstream**: L5 application skill. Load `prompt-forge` (L4) first for VRAM/recipe context
> before wiring the AnimaStandardV7 workflow — `prompt-forge/SKILL.md` step 7 routes here.

## 1. 任务

Stage 2 接受 Stage 0（项目骨架）和 Stage 1（LoRA 训练）的产出，**自动**完成：
1. 从 synopsis + character/scene 描述推断出 `01_plan.md` 镜头表
2. 用 **AnimaStandardV7.json** 工作流逐镜生成 PNG（仅修改 prompt + LoRA）
3. 自动调 manga-stage-3-review 内部 6 维算法 skill **6 维**评分（v2 起与 Stage 3 对齐）
4. 落盘到 `04_outputs/01_panels/` 和 `03_storyboard/02_panels/`
5. 维护 `manifest.json` 和 `pipeline_state.json`

**核心约束**：
- 工作流锁定为 `AnimaStandardV7.json`（73 节点），**不允许使用其他工作流**
- 仅允许修改 2 个节点的 widget：节点 3 (positive prompt) 和节点 4 (negative prompt)
- 禁止新增/删除节点
- 修改前备份，执行后恢复（遵循 `_shared/workflow_config_guard.md`）

**v2.0 角色一致性增强**（可选）：
- **默认**：B1 LoRA only（已有 3 个固定 LoRA）
- **可选 [PACK-CANDIDATE]**：叠加 IP-Adapter（`comfyui-anima-ipadapter` 不在 plugin ship 范围,需 `scripts/install.sh --with-anima-ipadapter` 选装）+ face attention（v2 提示，可在 metadata 标注启用但不默认打开）
- **P1.2 PhotoMaker V2**：单图 ID 嵌入替代 LoRA 训练（秒级，1 张参考图即可）

### PhotoMaker V2 替代/补充路径（v2.0 + P1.2）

| 路径 | 适用场景 | 训练成本 |
|------|---------|---------|
| **B1 LoRA only**（默认） | 多 panel 角色一致性 + 稳定 | 训 LoRA 1-2h |
| **B1 + IP-Adapter face** | 多 panel + 面部精确锁定 | 训 LoRA + IP-Adapter 推理 |
| **P1 PhotoMaker V2**（P1.2 新加） | **单 panel + 1 张参考图即可**，无需 LoRA 训练 | 0 训练，秒级 |

PhotoMaker V2 触发条件：
- 用户说"用 1 张照片生成 LoRA"/"no LoRA 训练"
- 或 `--identity-source single-image --reference <path>`
- 包：TencentARC/PhotoMaker-V2（Apache-2.0）+ ComfyUI 包装节点（待 `mcp__comfyui-mcp__search_custom_nodes` 验证）

**优势**：跳过整个 Stage 1（lora-trainer），适合"快速验证剧情面板"或"角色还没定稿"场景。
**限制**：跨 panel 一致性弱于 LoRA（无 batch 训练）；推荐作为 Stage 2 fallback 而非默认。

## 2. 端到端流程

```
Stage 0 输出                              Stage 1 输出
  ├─ 01_source/synopsis.md
  ├─ 02_assets/01_characters/<n>/
  │   └─ 02_descriptions/character_card.md
  ├─ 02_assets/02_scenes/<n>/
  ├─ 02_assets/04_styles/palette.md, camera.md
  └─ 03_storyboard/01_plan.md (可能空表)
                ↓
        ┌─────────────────────────┐
        │  Stage 2 — Director    │
        │  ensure-plan → parse    │
        │  validate → per-panel   │
        │  backup → modify → exec │
        │  restore → judge (6 维) │
        │  retry if < 7.0 (1 次)  │
        │  manifest + state       │
        └─────────────────────────┘
```

## 3. 架构：bash 调度 + Agent 执行

| 阶段 | 谁做 | 工具 |
|------|------|------|
| 解析 01_plan.md | bash | `scripts/parse-plan.sh` |
| 验证前置 | bash | `scripts/validate-preconditions.sh` |
| 推断镜头表（如空） | **Agent** | prompt-forge recipe auto-pull (via `skills/prompt-forge/internals/recipe_lookup.py`) |
| 备份工作流配置 | **Agent** | `mcp__comfyui-mcp__query_workflow` |
| 修改 prompt 节点 | **Agent** | `mcp__comfyui-mcp__modify_workflow`（仅节点 3、4） |
| 提交生成 | **Agent** | `mcp__comfyui-mcp__enqueue_workflow` |
| 等待完成 | **Agent** | `mcp__comfyui-mcp__get_job_status` |
| 拉图 | **Agent** | `mcp__comfyui-mcp__get_image` |
| 恢复工作流配置 | **Agent** | `mcp__comfyui-mcp__modify_workflow` |
| 评分 | **Agent** | manga-stage-3-review 内部 6 维算法（已 absorbed aesthetic-judge） |
| 落盘 | bash | `cp` + `Write` |

## 4. 输入参数

| 参数 | 必需 | 默认 | 说明 |
|------|------|------|------|
| `--project-root` | ✅ | - | 项目根 |
| `--resume` | ❌ | false | 续跑（跳过已完成）|
| `--panel` | ❌ | - | 单镜重跑 |
| `--auto-score` | ❌ | true | 自动评分 |
| `--retry-low` | ❌ | true | < 7.0 重试 1 次 |
| `--seed` | ❌ | 42 | 起始 seed |

**已移除**：`--arch`、`--width`/`--height`、`--workflow`（全部锁定）

## 5. 工作流配置（锁定）

### 工作流：`AnimaStandardV7.json`（73 节点）

### 可修改节点（白名单）— 仅 2 个

| 节点 ID | class_type | widget | 用途 |
|---------|-----------|--------|------|
| **3** | `ImpactWildcardProcessor` "POSITIVE" | `wildcard_text` | 正向提示词 |
| **4** | `ImpactWildcardProcessor` "NEGATIVE" | `wildcard_text` | 反向提示词 |

### 固定 LoRA（不可修改）

```
<lora:gpt-image-2_anima-base1_v1-1:0.80:0.80>
<lora:anima-base-1-masterpiece-v51:0.80>
<lora:细节调整:0.50>
```

### 固定采样参数

| 参数 | 值 | 节点 |
|------|-----|------|
| Steps | 30 | 24 |
| CFG | 4.5 | 24 |
| Sampler | dpmpp_2m | 24 |
| Scheduler | karras | 24 |
| Width | 832 | 39 |
| Height | 1216 | 47 |

## 6. Prompt 构造(prompt-forge recipes — 与 Stage 4 说话场景对齐)

> Plugin `prompt-forge` skill 在 2026-07-30 hard-delete(commit 531dd62)。
> 方法学保留于 `skills/prompt-forge/internals/legacy/prompt-forge-methodology.md`,
> 但运行时 recipe dialect 通过 `skills/prompt-forge/internals/recipe_lookup.py --model anima` 拉。

### 正向 prompt

使用 prompt-forge `recipes/MODELS.md` 的 Anima 预设（§B2）：

```
score_9, score_8_up, score_7_up,
[角色 tag], [外貌 tag], [服装 tag], [动作 tag],
[场景 tag], [光线 tag], [画师 tag],
[风格 tag]
```

### 反向 prompt

```
worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, lowres, censor
```

**v2 增强**：当 Stage 2 panel 对应 Stage 4 说话场景时，prompt 应**预留**嘴型/表情描述位，与 Stage 4 speaking 场景 prompt 对齐。

## 7. 配置守护 SOP

每 panel 生成遵循四步闭环：

```
Step 1: query_workflow(ids=["3","4"]) → 备份
Step 2: modify_workflow(ops=[改节点3,改节点4])
Step 3: enqueue_workflow → get_job_status → get_image
Step 4: modify_workflow(ops=[恢复节点3,恢复节点4]) → query_workflow 验证
```

## 8. 输出 schema（v2 已加 stage4_scene_type）

```json
{
  "project": "wuyin_jianxin",
  "workflow": "AnimaStandardV7.json",
  "workflow_locked": true,
  "width": 832,
  "height": 1216,
  "seed_base": 42,
  "generated_at": "2026-07-27T10:00:00",
  "panels": [
    {
      "id": 1,
      "scene": "京都夜樱",
      "characters": ["绯村剑心"],
      "prompt": "score_9, score_8_up, feicun_jianxin...",
      "negative": "worst quality, low quality...",
      "seed": 43,
      "output_path": "04_outputs/01_panels/scene_01.png",
      "scores": {
        "composition": 8,
        "lighting": 7,
        "color": 8,
        "detail": 7,
        "style": 9,
        "atmosphere": 8,
        "total": 7.8
      },
      "retry_count": 0,
      "verified": true,
      "config_restored": true,
      "stage4_scene_type": "normal"
    }
  ]
}
```

## 9. 失败处理

| 失败 | 策略 |
|------|------|
| 评分 < 7.0 | 调整 prompt，重试 1 次 |
| 重试仍 < 7.0 | 标 `verified: false` |
| OOM | 标 `failed: oom` |
| 配置恢复失败 | 记录错误，通知用户 |

## 10. 相关引用

- **上游**: `skills/prompt-forge/SKILL.md`（L4 — 必须先加载 for VRAM/recipe）
- 上游: `skills/manga-orchestrator/SKILL.md` (Stage 0) / `skills/lora-trainer/SKILL.md` (Stage 1)
- 下游: manga-stage-3-review 内部 6 维算法 (Stage 3) / `skills/manga-stage-3-review/SKILL.md` (Stage 4)
- 工作流: `_shared/workflow_resolver.md` §2
- 配置守护: `_shared/workflow_config_guard.md`
- 评分: 6 维（构图/光线/色彩/细节/风格/**氛围**），threshold 7.0

## 11. 版本

- v2.1.0（2026-07-30）：P1.1 ported — frontmatter 声明 prompt-forge 上游；路径全部改为 plugin 内
- v2.0.0（2026-07-27）：6 维评分对齐；schema 增 stage4_scene_type；预留嘴型描述位给 Stage 4 说话场景
- v1.1.0（旧）：5 维评分
