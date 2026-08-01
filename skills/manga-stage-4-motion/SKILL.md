---
name: manga-stage-4-motion
description: "AI 漫剧 Stage 4 — 视频生成（含说话场景）。主路锁定 ltx23AllInOneWorkflowForRTX_v44 工作流，统一处理所有视频：微动作、说话、环境音。备选 I2V_InfiniteTalk_Wan21（唇型驱动）。Also load prompt-forge first for VRAM/recipe context."
version: 3.1.0
author: Claude Code
triggers:
  - "生成视频"
  - "微动作"
  - "stage 4"
  - "图生视频"
  - "说话视频"
  - "加台词"
  - "唇型同步"
  - "talking head"
allowed-tools: Bash, Read, Write, "mcp__comfyui-mcp__*"
---

# Manga Stage 4 — 视频生成（含说话场景）v3.1, ported

> **Plugin path**: `skills/manga-stage-4-motion/SKILL.md`
> **Upstream**: L5 application skill. Load `prompt-forge` (L4) first for VRAM/recipe context
> before wiring the LTX workflow — `prompt-forge/SKILL.md` step 7 routes here for stage 4.

## 1. 概述

Stage 4 是**统一的视频生成阶段**，接受 Stage 3 审查通过的 PNG 面板，用 **ltx23AllInOneWorkflowForRTX_v44.json** 生成带音频的视频。

覆盖所有视频场景：
- **微动作**：环境氛围、运镜、动作
- **说话场景**：嘴型动作、表情、台词时序
- **纯氛围**：空镜、转场、环境音

**已合并原 Stage 5（说话头部）**，不再有独立的唇型同步阶段。

**v3.0 新增**：备选 `I2V_InfiniteTalk_Wan21.json` 工作流（Wan2.1-InfiniteTalk + wav2vec）作为专业唇型同步选项，仅当用户指定 `--lip-sync` 或 prompt 标记说话场景且 `stage4_scene_type=speaking` 且主路效果差时启用。

## 2. 端到端流程

```
Stage 3 verified panels
  → 判断场景类型（normal / speaking）
  → 构造对应 prompt（prompt-forge §14）
  → upload_image → modify 5 个白节点 → enqueue → get_image → scene_NN.mp4（含音频）

  (v3.0 备选: speaking 场景 + --lip-sync → 用 I2V_InfiniteTalk_Wan21 + 用户音频)
```

## 3. 工作流配置

### 3.1 主路工作流：`ltx23AllInOneWorkflowForRTX_v44.json`（78 节点）

详见 `_shared/workflow_resolver.md` §3。

| 节点 ID | class_type | widget | 用途 |
|---------|-----------|--------|------|
| **121** | `CLIPTextEncode` "positive" | `text` | 正向提示词 |
| **593** | `CLIPTextEncode` "negative" | `text` | 反向提示词 |
| **149** | `LoadImage` "First Frame" | `image` | 首帧图片 |
| **1792** | `PrimitiveInt` "Longer Edge" | `value` | 较长边分辨率（默认 2000）|
| **1793** | `PrimitiveInt` "Clip Length" | `value` | 时长秒（默认 10）|

### 3.2 备选工作流：`I2V_InfiniteTalk_Wan21.json`（v3 新增，唇型同步专用）

> **触发条件**：panel 标记 `stage4_scene_type=speaking` 且 `--lip-sync` 或自动检测到主路嘴型效果差且 `audio-path` 存在。

- 模型：`Wan2_1-InfiniteTalk_Single_Q6_K.gguf` + wav2vec
- 输入：首帧 PNG + 用户音频（mp3/wav）
- 输出：说话场景视频（带唇型同步）
- VRAM：~12GB（8GB 临界，需 blocks_swap）
- 不强制启用 — 默认仍走主路

### 3.3 备路工作流：`MAGI-1`（P1.1，2026-07-27 新增，8GB 多镜头友好）

> **触发条件**：用户 `--model magi1` 或自动检测 8GB 友好需求。

- 来源：Seaweed AI MAGI-1（Apache-2.0 开源，2026），chunk-wise 自回归
- 模型：`magi-1-q4_k.gguf`
- VRAM：**~8GB GGUF Q4**（8GB 卡唯一多镜头友好）
- 输入：首帧 PNG（multi-shot capable）
- 输出：mp4 视频
- 与主路区别：**chunk-wise 5-10s panel 衔接更自然；Q4 量化降低 8GB 卡门槛**
- 集成状态：**待 `mcp__comfyui-mcp__apply_manifest magi1` 或 `install_custom_node magi1`（暂无标准 pack 名）**

### 3.4 modify_workflow 模板（主路）

```python
operations = [
    {"op": "set_input", "node_id": "149", "input_name": "image", "value": first_frame},
    {"op": "set_input", "node_id": "121", "input_name": "text", "value": positive_prompt},
    {"op": "set_input", "node_id": "593", "input_name": "text", "value": negative_prompt},
    {"op": "set_input", "node_id": "1792", "input_name": "value", "value": longer_edge},
    {"op": "set_input", "node_id": "1793", "input_name": "value", "value": clip_length}
]
```

## 4. 场景分类与 Prompt 策略

### 场景类型判断（从 Stage 2 manifest 的 stage4_scene_type 字段）

| 镜头表标记 | 场景类型 | prompt 重点 |
|-----------|---------|------------|
| 动作/环境/空镜 | **normal** | 氛围、运镜、环境音 |
| 台词/对白/说话 | **speaking** | 嘴型、表情、台词时序 |

### 4a. normal 场景 prompt

```
[场景描述], [角色描述], [动作描述],
[运镜], [光线/氛围], [时序], [速度], [画质]
```

### 4b. speaking 场景 prompt（v3 加更精细的嘴型描述）

```
[角色描述], speaking [emotion], mouth opening and closing,
lips moving naturally, [facial expression],
[eyebrows], [肢体语言],
[运镜], [时序: 台词节奏 0-3s/3-6s/6-9s], [光线/氛围]
```

**说话场景关键维度**：

| 维度 | 描述词 |
|------|--------|
| 嘴型 | `mouth opening and closing, lips moving naturally, speaking animation` |
| 表情 | `determined expression, emotional eyes, eyebrows raised` |
| 肢体 | `slight head nod, hand gesture, body leaning forward` |
| 时序 | `0-3s: opens mouth to speak; 3-6s: speaks passionately; 6-9s: finishes, lips close` |
| 音频 | `with dialogue, [台词描述]`（注意：LTX 不直接接音频，需转写为描述；InfiniteTalk 备路可直接接） |

### 反向 prompt（通用）

```
animation, cartoon
```

## 5. 配置守护 SOP（4 步闭环）

```
Step 1: query_workflow(ids=["121","593","149","1792","1793"]) → 备份
Step 2: upload_image(首帧) → modify_workflow(5 个白节点)
Step 3: enqueue_workflow → get_job_status → get_image
Step 4: modify_workflow(恢复 5 个白节点) → query_workflow 验证
```

## 6. 输入参数（v3 增 lip-sync）

| 参数 | 必需 | 默认 | 说明 |
|------|------|------|------|
| `--project-root` | ✅ | - | 项目根 |
| `--resume` | ❌ | false | 续跑 |
| `--panel` | ❌ | - | 单 panel 重跑 |
| `--longer-edge` | ❌ | 2000 | 较长边分辨率 |
| `--clip-length` | ❌ | 10 | 时长秒 |
| `--scene-type` | ❌ | auto | `action` / `speaking` / `auto` |
| `--dialogue` | ❌ | 空 | speaking 场景的台词文本 |
| `--lip-sync` | ❌ | false | **v3 新** — 启用 I2V_InfiniteTalk_Wan21 备选 |
| `--audio-path` | ❌ | - | **v3 新** — 仅 --lip-sync 时需要；用户音频 |

## 7. 输出 schema（v3 增 lip_sync_used）

```json
{
  "workflow": "ltx23AllInOneWorkflowForRTX_v44.json",
  "workflow_locked": true,
  "scenes": [{
    "id": 1,
    "scene_type": "speaking",
    "input_panel": "04_outputs/01_panels/scene_01.png",
    "video_path": "04_outputs/02_micro_motion/scene_01.mp4",
    "prompt": "...",
    "dialogue": "我要打败你！",
    "duration": 10,
    "has_audio": true,
    "config_restored": true,
    "lip_sync_used": false,
    "fallback_workflow": null
  }]
}
```

## 8. 失败处理

| 失败 | 策略 |
|------|------|
| OOM | 降 longer_edge 到 1024，重试 1 次 |
| 超时（>10min） | 标 `failed: timeout` |
| speaking 嘴型效果差 | v3 自动尝试 I2V_InfiniteTalk_Wan21 备选（需 audio_path） |
| 配置恢复失败 | 记录错误，通知用户 |

## 9. 已知约束

1. **LTX 无专用唇型同步**：说话效果依赖 prompt 描述精度
2. **音频由 LTX 自动生成**：不能直接输入用户音频文件（用户音频需转写为 prompt）— **v3 备选工作流可解**
3. **Wan2.1-InfiniteTalk（备选）需要用户音频**：通过 `--audio-path` 传入
4. **说话场景复杂对白可能不理想**：先用主路 LTX，效果差则用备路 InfiniteTalk

## 10. v3 备选工作流集成（speaking 场景自动 fallback）

```
if scene_type == speaking:
  尝试主路 LTX
  if 嘴型效果差 AND audio_path 存在:
    启用 I2V_InfiniteTalk_Wan21
    加载用户音频 + 首帧
    → 输出真正唇型同步视频
```

## 11. 视频后处理（Stage 4 → Stage 5 之间，P1.4，2026-07-27 新增）

> **推荐**：低质量视频先过 `video-upscale` pack 再到 Stage 5 字幕拼接。

### video-upscale ComfyUI Pack（P1.4 集成）

- 来源：comfyui-mcp `video-upscale` skill（已就绪在 ComfyUI bundled list）
- 模型：SeedVR2（高精度）或 FlashVSR（快速）
- 触发：用户说"视频超分""放大视频""upscale 2x/4x"
- 调用：`mcp__comfyui-mcp__upscale_image` 或自定义 video upscale workflow
- pipeline 位置：**Stage 4 完成后 → Stage 5 之前**

### 集成方案

```bash
# Stage 4 输出 → upscale → Stage 5
scene_NN.mp4 (Stage 4)
  → video-upscale workflow (SeedVR2 2x)
    → scene_NN_2x.mp4 (Stage 5 输入)
```

P1.4 升级路径：
- [ ] 自动按 scene_NN 顺序批处理
- [ ] scale 选择（2x/4x）
- [ ] VRAM tier 自动选择（Q4 GGUF vs fp8 full）

## 12. 相关引用

- **上游**: `skills/prompt-forge/SKILL.md`（L4 — 必须先加载 for VRAM/recipe）
- 上游: `skills/manga-stage-3-review/SKILL.md` (Stage 3 审查)
- 下游: `skills/ffmpeg-pipeline/SKILL.md` (Stage 5 字幕)
- 工作流: `_shared/workflow_resolver.md` §3
- 配置守护: `_shared/workflow_config_guard.md`
- Prompt 框架: `prompt-forge` §14（视频 prompt）
- orchestrator: `skills/manga-orchestrator/SKILL.md` §4 Stage 4

## 13. 版本

- v3.1.0（2026-07-30）：P1.1 ported — frontmatter 声明 prompt-forge 上游；路径全部改为 plugin 内
- v3.0.0（2026-07-27）：新增 I2V_InfiniteTalk_Wan21 备选工作流（唇型同步）；`--lip-sync` / `--audio-path` 参数；输出 schema 增 `lip_sync_used` 字段
- v2.0.0（旧）：单一 LTX 一体方案
- v1.0.0：原 Stage 5 独立 skill
